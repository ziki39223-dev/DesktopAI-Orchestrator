"""后端层：Mock（开发机）与 Real（工作机）两套实现，共享同一接口。

纪律：
- ``mock`` 不得 import ``real``；
- ``real`` 的 Windows 专属依赖必须延迟导入（docs/07-decision-log.md ADR-009）。
"""

from __future__ import annotations

from .base import Backend

__all__ = ["Backend"]
