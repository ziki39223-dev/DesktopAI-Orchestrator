"""Mock 后端：开发机默认实现，零 Windows GUI 依赖。

行为：
- 窗口清单来自 ``window_rules.json``（没有则用内置默认三客户端）；
- ``send_prompt`` 记录轮次与 prompt，``fetch_output`` 按配置模拟"生成中→完成"；
- 支持失败注入，供编排侧容错联调。
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from ...config.rules import TargetRules, WindowRules
from ...config.settings import MockSettings
from ...contracts.constants import (
    COMPLETION_MARKER,
    WIN_KEYS,
    BackendKind,
    FetchStatus,
)
from ...contracts.errors import ErrorCode, ToolError
from ...contracts.tools import (
    FetchOutputData,
    ListTargetWindowsData,
    ReloadWindowRulesData,
    SendPromptData,
    WindowInfo,
)
from ..base import Backend, SendOutcome

_USER_MOCK = "【Mock 用户输入】"


@dataclass(slots=True)
class _ClientState:
    """单个客户端的 mock 会话状态。"""

    turns: deque[str] = field(default_factory=deque)
    poll_count: int = 0
    last_prompt: str = ""
    last_prompt_len: int = 0


class MockBackend(Backend):
    """可预期的模拟后端。"""

    kind = BackendKind.MOCK

    def __init__(
        self,
        *,
        rules: WindowRules,
        settings: MockSettings | None = None,
        rules_path: str = "config/window_rules.json",
    ) -> None:
        self._rules = rules
        self._settings = settings or MockSettings()
        self._rules_path = rules_path
        self._states: dict[str, _ClientState] = {key: _ClientState() for key in WIN_KEYS}
        self._lock = threading.Lock()
        self._turn_seq = 0

    # ------------------------------------------------------------------ 内部

    def _injected_error(self, win_key: str, stage: str) -> None:
        """按配置注入失败，模拟真实世界的异常分布。"""
        code = self._settings.inject_errors.get(f"{win_key}:{stage}") or self._settings.inject_errors.get(win_key)
        if not code:
            return
        try:
            error_code = ErrorCode(code)
        except ValueError as exc:
            raise ToolError(
                ErrorCode.RULES_INVALID,
                f"mock.inject_errors 里的错误码非法：{code}",
                detail={"win_key": win_key, "stage": stage},
            ) from exc
        raise ToolError(error_code, f"[mock] 注入失败 {win_key}/{stage}", detail={"win_key": win_key})

    def _rules_for(self, win_key: str) -> TargetRules:
        return self._rules.get(win_key)

    # ------------------------------------------------------------------ 工具

    def list_target_windows(self, *, include_unavailable: bool = False) -> ListTargetWindowsData:
        windows: list[WindowInfo] = []
        for index, win_key in enumerate(WIN_KEYS, start=1):
            target = self._rules.clients[win_key]
            windows.append(
                WindowInfo(
                    win_key=win_key,  # type: ignore[arg-type]
                    display_name=target.display_name,
                    matched=True,
                    hwnd=0x1000 + index,
                    title=f"[mock] {target.display_name}",
                    class_name=target.class_name or "Chrome_WidgetWin_1",
                    pid=10_000 + index,
                    ready=True,
                    notes="",
                )
            )
        # mock 下所有客户端恒可用，include_unavailable 只影响真实后端；
        # 保留参数语义一致性，便于编排侧两种模式共用同一套调用代码。
        _ = include_unavailable
        return ListTargetWindowsData(windows=windows)

    def send_prompt(
        self,
        *,
        win_key: str,
        prompt: str,
        append_marker: bool = True,
    ) -> SendOutcome:
        target = self._rules_for(win_key)
        self._injected_error(win_key, "send")

        if append_marker:
            marker_note = f"\n\n（完成后请在回答结尾单独输出：{target.completion_marker}）"
            full_prompt = prompt.rstrip() + marker_note
        else:
            full_prompt = prompt

        with self._lock:
            state = self._states[win_key]
            state.poll_count = 0
            state.last_prompt = full_prompt
            state.last_prompt_len = len(full_prompt)
            self._turn_seq += 1
            turn_id = f"t-{self._turn_seq:04d}"
            state.turns.append(turn_id)

        from ...common.text import now_local, preview

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
        target = self._rules_for(win_key)
        self._injected_error(win_key, "fetch")

        from ...common.text import truncate

        with self._lock:
            state = self._states[win_key]
            state.poll_count += 1
            poll_index = state.poll_count
            prompt_len = state.last_prompt_len
            turn_id = state.turns[-1] if state.turns else ""

        if self._settings.latency_s:
            time.sleep(min(self._settings.latency_s, 0.05))

        still_generating = poll_index <= self._settings.generating_polls
        if still_generating:
            partial = f"{_USER_MOCK}\n[mock] 正在生成第 {poll_index} 段…"
            text, truncated = truncate(partial, max_chars)
            return FetchOutputData(
                win_key=win_key,  # type: ignore[arg-type]
                status=FetchStatus.GENERATING,
                completed=False,
                marker_found=False,
                text=text,
                text_length=len(text),
                truncated=truncated,
                turn_id=turn_id,
            )

        body = (
            f"{_USER_MOCK}（{prompt_len} 字符）\n"
            f"[mock] 这是 {target.display_name} 的模拟回答，用于接口契约与编排流程联调。\n"
            f"要点一：契约字段与真实后端保持一致。\n"
            f"要点二：结束标记出现即视为完成。\n"
            f"{target.completion_marker}"
        )
        text, truncated = truncate(body, max_chars)
        marker_found = target.completion_marker in text
        return FetchOutputData(
            win_key=win_key,  # type: ignore[arg-type]
            status=FetchStatus.COMPLETED if marker_found else FetchStatus.IDLE,
            completed=marker_found,
            marker_found=marker_found,
            text=text,
            text_length=len(text),
            truncated=truncated,
            turn_id=turn_id,
        )

    def reload_window_rules(self, *, path: str | None = None) -> ReloadWindowRulesData:
        from ...config.rules import load_window_rules

        target_path = path or self._rules_path
        rules = load_window_rules(target_path)
        with self._lock:
            self._rules = rules
            self._rules_path = str(target_path)

        return ReloadWindowRulesData(
            loaded=True,
            path=str(target_path),
            rules_version=rules.rules_version,
            clients=rules.client_keys,
        )


__all__ = ["COMPLETION_MARKER", "MockBackend"]
