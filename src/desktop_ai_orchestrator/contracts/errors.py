"""错误码与结构化错误。

设计要点：
- 错误码集合冻结在 ``ErrorCode``，编排侧可只凭码决策；
- 任何失败都必须转成 ``ToolEnvelope(ok=False, error_code=...)``，禁止裸异常冒到 MCP 层；
- ``detail`` 只放排查用信息，不得含聊天正文（日志脱敏要求同源）。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    """工具错误码。一次失败只对应一个码，不做复合。"""

    OK = "OK"
    #: 入参校验失败（缺字段、类型不符、超长度等）。
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    #: 规则里匹配不到目标窗口，或配置的客户端未启动。
    WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
    #: 窗口在，但输入框/发送/输出区按规则全部策略都定位失败。
    CONTROL_NOT_FOUND = "CONTROL_NOT_FOUND"
    #: 已定位并写入，但触发发送失败。
    SEND_FAILED = "SEND_FAILED"
    #: 读输出区这个动作本身失败（不是"还没生成完"）。
    OUTPUT_TIMEOUT = "OUTPUT_TIMEOUT"
    #: 保留：需要显式表达"未完成且不可继续轮询"时使用；常规等待用 FetchStatus。
    NOT_COMPLETED = "NOT_COMPLETED"
    #: window_rules.json 结构/字段校验失败。
    RULES_INVALID = "RULES_INVALID"
    #: real 模式缺 Windows 专属依赖（开发机常见）。
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    #: 未分类内部错误，兜底用。
    INTERNAL_ERROR = "INTERNAL_ERROR"
    #: 当前模式不支持该操作（如 mock 下请求真实句柄）。
    MODE_MISMATCH = "MODE_MISMATCH"


class ToolErrorInfo(BaseModel):
    """出参里的错误明细，仅在 ``ok=False`` 时有意义。"""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    message: str = ""
    #: 排查用结构化上下文，例如失败的策略下标、窗口标题、规则字段路径。
    detail: dict[str, Any] = Field(default_factory=dict)


class ToolError(Exception):
    """后端抛出的受控错误，由工具层捕获并映射成出参错误码。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}

    def to_info(self) -> ToolErrorInfo:
        return ToolErrorInfo(code=self.code, message=self.message, detail=dict(self.detail))

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"ToolError(code={self.code.value!r}, message={self.message!r})"
