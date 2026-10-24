"""日志配置：标准库 logging + 结构化单行输出 + 可选文件落盘。"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
_configured = False

#: stdio 传输时 stdout 属于协议通道，日志必须只走 stderr。
_STDIO_SAFE_STREAM = sys.stderr


def configure_logging(
    *,
    level: str = "INFO",
    log_dir: str | Path | None = None,
    to_stderr: bool = True,
    force: bool = False,
) -> None:
    """初始化根 logger。

    Args:
        level: 日志级别字符串。
        log_dir: 非空时追加按天滚动的文件 handler。
        to_stderr: 是否输出到 stderr（stdio 模式必须为 True 且不能输出 stdout）。
        force: 重新配置（测试用）。
    """
    global _configured
    if _configured and not force:
        return

    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT)

    if to_stderr:
        stream_handler = logging.StreamHandler(_STDIO_SAFE_STREAM)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    if log_dir is not None:
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            directory / "orchestrator.log",
            when="midnight",
            backupCount=14,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # 第三方库的噪音压制
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)

    _configured = True


def bind_correlation_id(correlation_id: str) -> logging.LoggerAdapter[logging.Logger]:
    """返回带 ``cid`` 前缀的 logger，便于在同一次调用内串联日志。"""
    base = logging.getLogger("dao")
    return logging.LoggerAdapter(base, {"cid": correlation_id})


def get_logger(name: str = "dao") -> logging.Logger:
    return logging.getLogger(name)


__all__ = ["bind_correlation_id", "configure_logging", "get_logger"]
