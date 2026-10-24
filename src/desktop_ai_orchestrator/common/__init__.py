"""通用工具：无业务逻辑的纯函数与小工具。"""

from __future__ import annotations

from .ids import new_correlation_id
from .retry import retry_call
from .text import now_local, preview, strip_completion_marker, truncate

__all__ = [
    "new_correlation_id",
    "now_local",
    "preview",
    "retry_call",
    "strip_completion_marker",
    "truncate",
]
