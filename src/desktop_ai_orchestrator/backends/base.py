"""后端抽象接口。

工具层只依赖本接口，不感知 mock / real 的差异；路由层负责按 ``mode`` 产出实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..contracts.constants import BackendKind
from ..contracts.tools import (
    FetchOutputData,
    ListTargetWindowsData,
    ReloadWindowRulesData,
    SendPromptData,
)


@dataclass(slots=True)
class SendOutcome:
    """后端 send_prompt 的原始结果（工具层再包信封）。"""

    data: SendPromptData
    #: 后端内部的轮次标记，供 fetch_output 的 ``since_last_send`` 使用。
    turn_id: str


class Backend(ABC):
    """四个工具对应的后端能力。

    实现方约定：
    - 失败一律抛 :class:`~desktop_ai_orchestrator.contracts.errors.ToolError`；
    - 不自行生成 correlation_id / elapsed_ms（由工具层统一负责）；
    - 不打印日志到 stdout（stdio 传输下 stdout 是协议通道）。
    """

    kind: BackendKind

    @abstractmethod
    def list_target_windows(self, *, include_unavailable: bool = False) -> ListTargetWindowsData:
        """枚举可识别的目标客户端窗口。"""

    @abstractmethod
    def send_prompt(
        self,
        *,
        win_key: str,
        prompt: str,
        append_marker: bool = True,
    ) -> SendOutcome:
        """向目标窗口输入框写入 prompt 并触发发送。"""

    @abstractmethod
    def fetch_output(
        self,
        *,
        win_key: str,
        timeout_s: float,
        since_last_send: bool = True,
        max_chars: int = 20_000,
    ) -> FetchOutputData:
        """读取聊天区输出并判断是否已出现结束标记。"""

    @abstractmethod
    def reload_window_rules(self, *, path: str | None = None) -> ReloadWindowRulesData:
        """重载控件规则文件。"""
