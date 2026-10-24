"""契约层：工具入参/出参、错误码、全局常量。

约束（见 docs/04-dev-rules.md §1）：
- 本包只允许依赖标准库与 pydantic；
- 禁止 import 本项目其它层（contracts 是被依赖方，不得反向依赖）。
- 冻结后字段只增不改不删。
"""

from __future__ import annotations

from .constants import (
    COMPLETION_MARKER,
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_TIMEOUT_S,
    MAX_TIMEOUT_S,
    WIN_KEYS,
    BackendKind,
    FetchStatus,
    WinKey,
)
from .errors import ErrorCode, ToolError, ToolErrorInfo
from .tools import (
    FetchOutputData,
    FetchOutputRequest,
    ListTargetWindowsData,
    ListTargetWindowsRequest,
    ReloadWindowRulesData,
    ReloadWindowRulesRequest,
    SendPromptData,
    SendPromptRequest,
    ToolEnvelope,
    WindowInfo,
)

__all__ = [
    "COMPLETION_MARKER",
    "DEFAULT_MAX_PROMPT_CHARS",
    "DEFAULT_TIMEOUT_S",
    "MAX_TIMEOUT_S",
    "WIN_KEYS",
    "BackendKind",
    "ErrorCode",
    "FetchOutputData",
    "FetchOutputRequest",
    "FetchStatus",
    "ListTargetWindowsData",
    "ListTargetWindowsRequest",
    "ReloadWindowRulesData",
    "ReloadWindowRulesRequest",
    "SendPromptData",
    "SendPromptRequest",
    "ToolEnvelope",
    "ToolError",
    "ToolErrorInfo",
    "WinKey",
    "WindowInfo",
]
