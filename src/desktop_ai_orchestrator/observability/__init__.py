"""结构化观测：日志、耗时、工具调用追踪。

纪律（docs/04-dev-rules.md §4）：
- 禁止 print，一律走 logger；
- 日志只打 prompt 长度 + 前 40 字摘要，不打正文；
- "未完成/超时"是正常状态，用 INFO 记录，不打 ERROR。
"""

from __future__ import annotations

from .logging import bind_correlation_id, configure_logging, get_logger
from .timing import Stopwatch

__all__ = ["Stopwatch", "bind_correlation_id", "configure_logging", "get_logger"]
