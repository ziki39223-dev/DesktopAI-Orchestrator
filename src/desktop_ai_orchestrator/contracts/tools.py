"""四个 MCP 工具的入参 / 出参契约。

冻结规则（docs/04-dev-rules.md §1）：工具名、字段名、错误码只增不改不删。
Mock 后端与 Real 后端必须实现完全相同的出参结构，差异只在数据来源与错误分布。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import (
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_TIMEOUT_S,
    MAX_TIMEOUT_S,
    BackendKind,
    FetchStatus,
    WinKey,
)
from .errors import ErrorCode, ToolErrorInfo


class _Strict(BaseModel):
    """所有契约模型的公共配置：禁止多余字段，保证契约即文档。"""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# 公共信封
# --------------------------------------------------------------------------- #


class ToolEnvelope[DataT](_Strict):
    """所有工具统一出参信封。

    ``ok=False`` 时 ``data`` 为 ``None`` 且 ``error`` 有值；``ok=True`` 时 ``error`` 为 ``None``。
    """

    ok: bool = True
    error_code: ErrorCode = ErrorCode.OK
    message: str = ""
    backend: BackendKind = BackendKind.MOCK
    correlation_id: str = ""
    elapsed_ms: int = 0
    error: ToolErrorInfo | None = None
    data: DataT | None = None


# --------------------------------------------------------------------------- #
# 1. list_target_windows
# --------------------------------------------------------------------------- #


class ListTargetWindowsRequest(_Strict):
    include_unavailable: bool = Field(
        default=False,
        description="是否返回未启动/未匹配到窗口的客户端（默认 False，只返回可用的）。",
    )


class WindowInfo(_Strict):
    win_key: WinKey
    display_name: str
    matched: bool = Field(description="是否在系统中命中该客户端窗口")
    hwnd: int | None = Field(default=None, description="窗口句柄；mock 模式下为伪造值")
    title: str = ""
    class_name: str = ""
    pid: int = 0
    ready: bool = Field(description="输入框与输出区是否都可定位（mock 恒 True）")
    notes: str = Field(default="", description="不可用原因摘要")


class ListTargetWindowsData(_Strict):
    windows: list[WindowInfo] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 2. send_prompt
# --------------------------------------------------------------------------- #


class SendPromptRequest(_Strict):
    win_key: WinKey
    prompt: str = Field(min_length=1, max_length=DEFAULT_MAX_PROMPT_CHARS)
    append_marker: bool = Field(
        default=True,
        description="是否由服务端在 prompt 尾部自动追加结束标记约定，默认追加。",
    )

    @field_validator("prompt")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt 不能为空白")
        return value


class SendPromptData(_Strict):
    win_key: WinKey
    sent: bool
    prompt_preview: str = Field(description="入参摘要（前 40 字），不含完整正文")
    prompt_length: int
    sent_at: datetime


# --------------------------------------------------------------------------- #
# 3. fetch_output
# --------------------------------------------------------------------------- #


class FetchOutputRequest(_Strict):
    win_key: WinKey
    timeout_s: float = Field(default=DEFAULT_TIMEOUT_S, gt=0, le=MAX_TIMEOUT_S)
    since_last_send: bool = Field(
        default=True,
        description="只取上一次 send_prompt 之后的新增内容，避免读到历史对话。",
    )
    max_chars: int = Field(default=DEFAULT_MAX_PROMPT_CHARS, gt=0)


class FetchOutputData(_Strict):
    win_key: WinKey
    status: FetchStatus
    completed: bool
    marker_found: bool
    text: str = ""
    text_length: int = 0
    truncated: bool = False
    turn_id: str = ""


# --------------------------------------------------------------------------- #
# 4. reload_window_rules
# --------------------------------------------------------------------------- #


class ReloadWindowRulesRequest(_Strict):
    path: str | None = Field(
        default=None,
        description="规则文件路径；为空则重载默认 config/window_rules.json。",
    )


class ReloadWindowRulesData(_Strict):
    loaded: bool
    path: str
    rules_version: str = ""
    clients: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 便捷构造函数
# --------------------------------------------------------------------------- #


def success_envelope[DataT](
    data: DataT,
    *,
    backend: BackendKind,
    correlation_id: str,
    elapsed_ms: int,
    message: str = "",
) -> ToolEnvelope[DataT]:
    """构造成功信封。"""
    return ToolEnvelope[DataT](
        ok=True,
        error_code=ErrorCode.OK,
        message=message,
        backend=backend,
        correlation_id=correlation_id,
        elapsed_ms=elapsed_ms,
        error=None,
        data=data,
    )


def failure_envelope(
    error: ToolErrorInfo,
    *,
    backend: BackendKind,
    correlation_id: str,
    elapsed_ms: int,
) -> ToolEnvelope[Any]:
    """构造失败信封；``data`` 恒为 None。"""
    return ToolEnvelope[Any](
        ok=False,
        error_code=error.code,
        message=error.message,
        backend=backend,
        correlation_id=correlation_id,
        elapsed_ms=elapsed_ms,
        error=error,
        data=None,
    )
