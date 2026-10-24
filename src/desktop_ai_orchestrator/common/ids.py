"""关联 ID 生成：贯穿一次工具调用的日志与出参。"""

from __future__ import annotations

import itertools
import secrets
import time

_counter = itertools.count(1)


def new_correlation_id(prefix: str = "c") -> str:
    """生成短小、可读、单进程内唯一的关联 ID，例如 ``c-1a2b3c4d-000007``。"""
    epoch = int(time.time()) & 0xFFFFFFFF
    return f"{prefix}-{epoch:08x}-{secrets.token_hex(2)}-{next(_counter):06d}"
