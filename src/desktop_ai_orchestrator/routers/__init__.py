"""路由层：按 ``mode`` 产出后端实例。

唯一职责是“选择实现”，不含任何工具业务逻辑（docs/03-directory-layout.md §2）。
"""

from __future__ import annotations

from .backend_router import BackendRouter, build_backend

__all__ = ["BackendRouter", "build_backend"]
