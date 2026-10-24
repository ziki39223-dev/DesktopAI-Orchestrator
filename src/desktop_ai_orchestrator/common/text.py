"""文本处理：脱敏预览、截断、结束标记处理。"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from ..contracts.constants import COMPLETION_MARKER

#: 日志/出参里 prompt 预览的最大字符数（docs/04-dev-rules.md §4.2）。
PREVIEW_CHARS: Final[int] = 40


def preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    """生成正文摘要：折叠空白 + 截断，避免把客户内容完整落盘。"""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "…"


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """按字符数截断，返回 ``(文本, 是否被截断)``。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def strip_completion_marker(text: str, marker: str = COMPLETION_MARKER) -> str:
    """去掉行尾的结束标记，便于编排侧直接使用正文。"""
    stripped = text.rstrip()
    if stripped.endswith(marker):
        return stripped[: -len(marker)].rstrip()
    return text


def now_local() -> datetime:
    """带本地时区的当前时间（出参 `sent_at` 等字段使用）。"""
    return datetime.now().astimezone()
