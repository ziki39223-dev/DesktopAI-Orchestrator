"""Real 后端的驱动接口：把"怎么碰 Windows"抽成可替换的实现。

好处：
- 开发机可以用 ``FakeDriver`` 做单测，不需要 Windows/UIA；
- 工作机用 ``WindowsDriver`` 真实操作，两者接口一致；
- 捕获能力作为可选扩展方法，UIA 失效时用于取证与降级。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ...config.rules import Strategy, TargetRules

#: 驱动私有的控件对象（UIA Control / FakeControl 等）。
#: 这里有意用 Any：不同驱动的控件类型完全不同，接口只需要"能传回去"。
type Control = Any


@dataclass(slots=True, frozen=True)
class WindowSnapshot:
    """一次窗口枚举的结果快照。"""

    win_key: str
    display_name: str
    hwnd: int
    title: str
    class_name: str
    pid: int
    matched: bool


class WindowDriver(ABC):
    """对某个目标客户端窗口的最小操作集。"""

    @abstractmethod
    def enumerate_targets(self, rules: dict[str, TargetRules]) -> list[WindowSnapshot]:
        """按规则匹配出目标窗口（每个 win_key 最多一个，一期单窗口）。"""

    @abstractmethod
    def locate(self, hwnd: int, strategies: list[Strategy]) -> Control | None:
        """按降级链定位控件，返回驱动自身的控件对象；全失败返回 None。"""

    @abstractmethod
    def write_text(self, control: Control, text: str) -> None:
        """把文本写入输入控件（优先 SetValue 语义，不触发逐字键盘输入）。"""

    @abstractmethod
    def trigger_send(self, hwnd: int, strategies: list[Strategy]) -> None:
        """触发发送（快捷键或点击发送按钮）。"""

    @abstractmethod
    def read_text(self, control: Control) -> str:
        """读取控件文本（输出区整段内容）。"""

    # 可选能力：画面捕获，默认不支持，由 WindowsDriver 覆盖。
    def capture_frame(self, hwnd: int) -> bytes | None:
        """捕获窗口画面（PNG 字节）。默认返回 None，表示当前驱动不支持。"""
        return None
