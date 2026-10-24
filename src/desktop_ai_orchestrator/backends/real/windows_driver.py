"""基于 Windows UIA 的真实驱动实现。

所有 Windows 依赖延迟导入；任一依赖缺失即抛 ``DEPENDENCY_MISSING``，
保证开发机能 import 本模块（只是不能实例化）。
"""

from __future__ import annotations

import logging
from typing import Any

from ...config.rules import Strategy, TargetRules
from ...contracts.errors import ErrorCode, ToolError
from . import deps
from .driver import Control, WindowDriver, WindowSnapshot

_log = logging.getLogger("dao.backends.real.windows_driver")


class WindowsDriver(WindowDriver):
    """用 ``uiautomation`` + ``win32gui`` 实现驱动接口。"""

    def __init__(self) -> None:
        if not deps.is_windows():
            raise ToolError(
                ErrorCode.DEPENDENCY_MISSING,
                "real 模式只能在 Windows 上运行",
                detail={"platform": "not-win32"},
            )
        self._auto = deps.require("uiautomation")
        self._gui = deps.require("win32gui")
        self._capture: Any = None  # 首次使用时再加载 windows_capture

    # ---------------------------------------------------------------- 枚举

    def enumerate_targets(self, rules: dict[str, TargetRules]) -> list[WindowSnapshot]:
        gui = self._gui
        found: dict[str, WindowSnapshot] = {}

        windows: list[tuple[int, str]] = []

        def _collect(hwnd: int, _extra: Any) -> bool:
            if not gui.IsWindowVisible(hwnd):
                return True
            title = gui.GetWindowText(hwnd)
            if title:
                windows.append((hwnd, title))
            return True

        gui.EnumWindows(_collect, None)

        for hwnd, title in windows:
            class_name = gui.GetClassName(hwnd)
            pid = self._pid_of(hwnd)
            for win_key, target in rules.items():
                if win_key in found:
                    continue
                if target.class_name and class_name != target.class_name:
                    continue
                if not any(keyword in title for keyword in target.title_keywords):
                    continue
                found[win_key] = WindowSnapshot(
                    win_key=win_key,
                    display_name=target.display_name,
                    hwnd=hwnd,
                    title=title,
                    class_name=class_name,
                    pid=pid,
                    matched=True,
                )
                break

        return list(found.values())

    def _pid_of(self, hwnd: int) -> int:
        try:
            import win32process  # 延迟导入：仅此处需要

            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            return int(pid)
        except ImportError:  # pragma: no cover - pywin32 缺失时降级
            return 0

    # ---------------------------------------------------------------- 控件

    def locate(self, hwnd: int, strategies: list[Strategy]) -> Control | None:
        auto = self._auto
        try:
            root = auto.ControlFromHandle(hwnd)
        except Exception as exc:  # UIA 树尚未就绪
            _log.debug("ControlFromHandle 失败 hwnd=%s: %s", hwnd, exc)
            return None
        if root is None:
            return None

        for strategy in strategies:
            control = self._locate_one(root, strategy)
            if control is not None:
                return control
        return None

    def _locate_one(self, root: Any, strategy: Strategy) -> Any | None:
        auto = self._auto
        try:
            if strategy.type == "automation_id":
                return root.Control(AutomationId=strategy.value)
            if strategy.type == "name":
                return root.Control(Name=strategy.value)
            if strategy.type == "control_type":
                controls = root.GetChildren()
                wanted = strategy.value.capitalize()
                matched = [c for c in controls if c.ControlTypeName == f"{wanted}Control"]
                index = strategy.index or 0
                return matched[index] if index < len(matched) else None
            if strategy.type == "class_name":
                return root.Control(ClassName=strategy.value)
            if strategy.type == "accelerator":
                return None  # 快捷键策略不产生控件对象
        except Exception as exc:  # 单条策略失败不影响后续降级
            _log.debug("策略 %s=%s 定位失败: %s", strategy.type, strategy.value, exc)
            return None
        _ = auto
        return None

    def write_text(self, control: Control, text: str) -> None:
        value_pattern = getattr(control, "GetValuePattern", None)
        try:
            if callable(value_pattern):
                value_pattern().SetValue(text)
                return
        except Exception as exc:  # 部分 Electron 输入框不支持 ValuePattern
            _log.debug("ValuePattern 写入失败，降级为 SendKeys: %s", exc)

        try:
            control.SetFocus()
            self._auto.SendKeys(text, waitTime=0.01, interval=0.001)
        except Exception as exc:
            raise ToolError(
                ErrorCode.SEND_FAILED,
                "写入输入框失败",
                detail={"reason": str(exc)},
            ) from exc

    def trigger_send(self, hwnd: int, strategies: list[Strategy]) -> None:
        for strategy in strategies:
            if strategy.type == "accelerator":
                try:
                    target = self._auto.ControlFromHandle(hwnd)
                    if target is not None:
                        target.SetFocus()
                    self._auto.SendKeys(strategy.value, waitTime=0.01)
                    return
                except Exception as exc:
                    _log.debug("快捷键发送失败 %s: %s", strategy.value, exc)
                    continue

            control = self.locate(hwnd, [strategy])
            if control is None:
                continue
            try:
                control.Click()
                return
            except Exception as exc:
                _log.debug("点击发送按钮失败: %s", exc)

        raise ToolError(
            ErrorCode.SEND_FAILED,
            "所有发送策略均失败",
            detail={"strategies": [f"{s.type}:{s.value}" for s in strategies]},
        )

    def read_text(self, control: Control) -> str:
        try:
            value_pattern = getattr(control, "GetValuePattern", None)
            if callable(value_pattern):
                return str(value_pattern().Value or "")
        except Exception as exc:
            _log.debug("ValuePattern 读取失败，降级 TextPattern: %s", exc)

        try:
            return str(control.GetTextPattern().DocumentRange.GetText(-1) or "")
        except Exception as exc:
            raise ToolError(
                ErrorCode.OUTPUT_TIMEOUT,
                "读取输出区文本失败",
                detail={"reason": str(exc)},
            ) from exc

    # ---------------------------------------------------------------- 捕获

    def capture_frame(self, hwnd: int) -> bytes | None:
        """DXGI / Windows Graphics Capture 抓帧（后台/最小化可用性由实测决定）。"""
        if self._capture is None:
            try:
                self._capture = deps.require("windows_capture")
            except ToolError:
                _log.info("windows-capture 不可用，跳过画面捕获")
                self._capture = False
        if self._capture is False:
            return None
        # 具体抓帧调用在 P2 按 windows-capture 实际 API 落地；此处保持接口稳定。
        _log.debug("capture_frame 尚未接线 hwnd=%s", hwnd)
        return None
