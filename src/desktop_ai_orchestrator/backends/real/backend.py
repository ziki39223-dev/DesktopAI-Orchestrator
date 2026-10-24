"""Real 后端：把驱动能力拼成四个工具语义。

职责边界：本层只做"编排流程"（找窗口 → 定位 → 写入 → 发送 → 轮询读），
具体 Windows 调用全部委托给 :class:`WindowDriver`，便于开发机用假驱动单测。
"""

from __future__ import annotations

import logging
import time

from ...common.text import now_local, preview, truncate
from ...config.rules import TargetRules, WindowRules
from ...config.settings import RealSettings
from ...contracts.constants import WIN_KEYS, BackendKind, FetchStatus
from ...contracts.errors import ErrorCode, ToolError
from ...contracts.tools import (
    FetchOutputData,
    ListTargetWindowsData,
    ReloadWindowRulesData,
    SendPromptData,
    WindowInfo,
)
from ..base import Backend, SendOutcome
from .driver import Control, WindowDriver, WindowSnapshot

_log = logging.getLogger("dao.backends.real")

#: 轮询下限，避免配置成 0 时空转占满 CPU。
_MIN_POLL_INTERVAL_S = 0.01


class RealBackend(Backend):
    """真机后端。"""

    kind = BackendKind.REAL

    def __init__(
        self,
        *,
        rules: WindowRules,
        driver: WindowDriver,
        settings: RealSettings | None = None,
        rules_path: str = "config/window_rules.json",
    ) -> None:
        self._rules = rules
        self._driver = driver
        self._settings = settings or RealSettings()
        self._rules_path = rules_path
        self._last_sent: dict[str, str] = {}
        self._turn_seq = 0

    # ---------------------------------------------------------------- 内部

    def _snapshot(self, win_key: str) -> WindowSnapshot:
        """取目标窗口快照，匹配不到抛 WINDOW_NOT_FOUND。"""
        target = self._rules.get(win_key)
        snapshots = self._driver.enumerate_targets({win_key: target})
        if not snapshots:
            raise ToolError(
                ErrorCode.WINDOW_NOT_FOUND,
                f"未找到 {target.display_name} 窗口，请确认客户端已启动",
                detail={"win_key": win_key, "title_keywords": target.title_keywords},
            )
        return snapshots[0]

    def _locate_with_retry(self, hwnd: int, target: TargetRules, field: str) -> Control:
        """按降级链定位控件；"返回 None" 也要重试，因此不用通用 retry_call。"""
        strategies = getattr(target, field)
        attempts = max(1, self._settings.locate_attempts)

        for attempt in range(1, attempts + 1):
            control = self._driver.locate(hwnd, strategies)
            if control is not None:
                return control
            if attempt < attempts:
                # UIA 树刷新/窗口刚获得焦点时首次定位常失败，短暂等待后重试。
                time.sleep(self._settings.locate_delay_s)

        raise ToolError(
            ErrorCode.CONTROL_NOT_FOUND,
            f"{target.display_name} 的 {field} 控件定位失败，"
            f"请用 Inspect.exe 重新采集并更新 window_rules.json",
            detail={
                "win_key": target.display_name,
                "field": field,
                "attempts": attempts,
                "strategies": [f"{s.type}:{s.value}" for s in strategies],
            },
        )

    # ---------------------------------------------------------------- 工具

    def list_target_windows(self, *, include_unavailable: bool = False) -> ListTargetWindowsData:
        snapshots = {
            snap.win_key: snap for snap in self._driver.enumerate_targets(dict(self._rules.clients))
        }
        windows: list[WindowInfo] = []
        for win_key in WIN_KEYS:
            target = self._rules.clients[win_key]
            snap = snapshots.get(win_key)
            if snap is None:
                if include_unavailable:
                    windows.append(
                        WindowInfo(
                            win_key=win_key,  # type: ignore[arg-type]
                            display_name=target.display_name,
                            matched=False,
                            ready=False,
                            notes="未检测到窗口",
                        )
                    )
                continue

            ready, notes = self._probe_ready(snap.hwnd, target)
            if not ready and not include_unavailable:
                continue
            windows.append(
                WindowInfo(
                    win_key=win_key,  # type: ignore[arg-type]
                    display_name=target.display_name,
                    matched=True,
                    hwnd=snap.hwnd,
                    title=snap.title,
                    class_name=snap.class_name,
                    pid=snap.pid,
                    ready=ready,
                    notes=notes,
                )
            )
        return ListTargetWindowsData(windows=windows)

    def _probe_ready(self, hwnd: int, target: TargetRules) -> tuple[bool, str]:
        """探测输入框与输出区是否可定位，作为 ready 判定。"""
        try:
            input_ok = self._driver.locate(hwnd, target.input) is not None
            output_ok = self._driver.locate(hwnd, target.output) is not None
        except ToolError as exc:
            return False, exc.message
        if input_ok and output_ok:
            return True, ""
        missing = []
        if not input_ok:
            missing.append("输入框")
        if not output_ok:
            missing.append("输出区")
        return False, "控件未定位：" + "、".join(missing)

    def send_prompt(
        self,
        *,
        win_key: str,
        prompt: str,
        append_marker: bool = True,
    ) -> SendOutcome:
        target = self._rules.get(win_key)
        snap = self._snapshot(win_key)
        input_control = self._locate_with_retry(snap.hwnd, target, "input")

        if append_marker:
            full_prompt = (
                prompt.rstrip()
                + f"\n\n（完成后请在回答结尾单独输出：{target.completion_marker}）"
            )
        else:
            full_prompt = prompt

        self._driver.write_text(input_control, full_prompt)

        if self._settings.send_confirm_s > 0:
            time.sleep(self._settings.send_confirm_s)

        self._driver.trigger_send(snap.hwnd, target.send)

        self._turn_seq += 1
        turn_id = f"t-{self._turn_seq:04d}"
        self._last_sent[win_key] = turn_id

        data = SendPromptData(
            win_key=win_key,  # type: ignore[arg-type]
            sent=True,
            prompt_preview=preview(prompt),
            prompt_length=len(full_prompt),
            sent_at=now_local(),
        )
        return SendOutcome(data=data, turn_id=turn_id)

    def fetch_output(
        self,
        *,
        win_key: str,
        timeout_s: float,
        since_last_send: bool = True,
        max_chars: int = 20_000,
    ) -> FetchOutputData:
        target = self._rules.get(win_key)
        snap = self._snapshot(win_key)
        output_control = self._locate_with_retry(snap.hwnd, target, "output")

        deadline = time.monotonic() + timeout_s
        marker = target.completion_marker
        last_len = 0
        text = ""

        while True:
            raw = self._driver.read_text(output_control)
            if len(raw) > max_chars:
                text, truncated = truncate(raw, max_chars)
            else:
                text, truncated = raw, False

            marker_found = marker in raw
            if marker_found:
                return FetchOutputData(
                    win_key=win_key,  # type: ignore[arg-type]
                    status=FetchStatus.COMPLETED,
                    completed=True,
                    marker_found=True,
                    text=text,
                    text_length=len(text),
                    truncated=truncated,
                    turn_id=self._last_sent.get(win_key, "") if since_last_send else "",
                )

            progressed = len(raw) > last_len
            last_len = len(raw)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return FetchOutputData(
                    win_key=win_key,  # type: ignore[arg-type]
                    status=FetchStatus.TIMEOUT,
                    completed=False,
                    marker_found=False,
                    text=text,
                    text_length=len(text),
                    truncated=truncated,
                    turn_id=self._last_sent.get(win_key, "") if since_last_send else "",
                )

            time.sleep(min(max(self._settings.poll_interval_s, _MIN_POLL_INTERVAL_S), remaining))
            _ = progressed

    def reload_window_rules(self, *, path: str | None = None) -> ReloadWindowRulesData:
        from ...config.rules import load_window_rules

        target_path = path or self._rules_path
        rules = load_window_rules(target_path)
        self._rules = rules
        self._rules_path = str(target_path)
        return ReloadWindowRulesData(
            loaded=True,
            path=str(target_path),
            rules_version=rules.rules_version,
            clients=rules.client_keys,
        )
