"""服务装配层：MCP Server 实例、工具注册、生命周期。

本层不认识 mock / real，只认识 ``ToolService``。
"""

from __future__ import annotations

from .app import build_server, server_lifespan

__all__ = ["build_server", "server_lifespan"]
