"""存储型 Fake 驱动：让 Real 后端的编排流程可在开发机上测试（无需 Windows/UIA）。

匹配规则刻意保持简单可预期：
- 策略 ``value`` 就是控件槽位名（``input`` / ``output`` / ``send``）；
- 槽位值为 ``None`` 表示该控件"采集失效"，用来触发 ``CONTROL_NOT_FOUND``；
- ``accelerator`` 策略不产生控件对象，直接计入发送调用。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from desktop_ai_orchestrator.backends.real.driver import WindowDriver, WindowSnapshot
from desktop_ai_orchestrator.config.rules import Strategy, TargetRules
from desktop_ai_orchestrator.contracts.constants import COMPLETION_MARKER

#: 允许的控件槽位名。
SLOTS: tuple[str, ...] = ("input", "output", "send")


@dataclass
class FakeControl:
    """模拟控件对象：只带一个可读写的文本值。"""

    text: str = ""
    kind: str = "edit"


@dataclass
class FakeWindow:
    """一个假窗口及其三个控件槽位。"""

    win_key: str
    hwnd: int
    title: str
    class_name: str = "Chrome_WidgetWin_1"
    pid: int = 4242
    input: FakeControl | None = field(default_factory=FakeControl)
    output: FakeControl | None = field(default_factory=FakeControl)
    send: FakeControl | None = field(default_factory=FakeControl)

    def slot(self, name: str) -> FakeControl | None:
        if name not in SLOTS:
            return None
        return getattr(self, name)


class FakeDriver(WindowDriver):
    """按预设数据响应所有驱动调用，并记录调用轨迹。"""

    def __init__(
        self,
        *,
        windows: dict[str, FakeWindow] | None = None,
        output_script: list[str] | None = None,
    ) -> None:
        self.windows: dict[str, FakeWindow] = windows or {}
        #: 每次 ``read_text`` 依次返回下一段；用尽后重复最后一段。
        #: 用于模拟"生成中 → 出现结束标记"的渐进过程。
        self.output_script: list[str] = list(output_script or [])
        self.read_index = 0
        self.written: list[str] = []
        self.send_count = 0
        self.locate_calls: list[str] = []

    # ---------------------------------------------------------------- 接口

    def enumerate_targets(self, rules: dict[str, TargetRules]) -> list[WindowSnapshot]:
        snapshots: list[WindowSnapshot] = []
        for win_key, target in rules.items():
            window = self.windows.get(win_key)
            if window is None:
                continue
            if target.class_name and window.class_name != target.class_name:
                continue
            if not any(keyword in window.title for keyword in target.title_keywords):
                continue
            snapshots.append(
                WindowSnapshot(
                    win_key=win_key,
                    display_name=target.display_name,
                    hwnd=window.hwnd,
                    title=window.title,
                    class_name=window.class_name,
                    pid=window.pid,
                    matched=True,
                )
            )
        return snapshots

    def locate(self, hwnd: int, strategies: list[Strategy]) -> object | None:
        window = self._window_by_hwnd(hwnd)
        if window is None:
            return None
        for strategy in strategies:
            if strategy.type == "accelerator":
                continue
            self.locate_calls.append(strategy.value)
            control = window.slot(strategy.value)
            if control is not None:
                return control
        return None

    def write_text(self, control: object, text: str) -> None:
        assert isinstance(control, FakeControl)
        control.text = text
        self.written.append(text)

    def trigger_send(self, hwnd: int, strategies: list[Strategy]) -> None:
        window = self._window_by_hwnd(hwnd)
        assert window is not None, f"未知 hwnd={hwnd}"
        self.send_count += 1
        # 贴近真实行为：发送后客户端生成回答，输出区出现正文 + 结束标记。
        # 若测试已通过 output_script 指定了渐进脚本，则以脚本为准，这里不覆盖。
        if window.output is not None and not window.output.text and not self.output_script:
            window.output.text = f"[fake] 已收到 {len(self.written)} 条输入\n{COMPLETION_MARKER}"

    def read_text(self, control: object) -> str:
        assert isinstance(control, FakeControl)
        if not self.output_script:
            return control.text
        index = min(self.read_index, len(self.output_script) - 1)
        self.read_index += 1
        return self.output_script[index]

    # ---------------------------------------------------------------- 辅助

    def _window_by_hwnd(self, hwnd: int) -> FakeWindow | None:
        for window in self.windows.values():
            if window.hwnd == hwnd:
                return window
        return None


__all__ = ["SLOTS", "FakeControl", "FakeDriver", "FakeWindow"]
