"""Real 后端：Windows UIA + 窗口捕获（工作机启用）。

纪律：
- 所有 Windows 专属库在函数内延迟导入，缺失时抛 ``DEPENDENCY_MISSING``；
- 不抓包、不逆向、不注入客户端进程（docs/01-requirements-baseline.md §7）；
- 任何 Windows 调用点都要有显式错误码，禁止 ``except: pass``。
"""

from __future__ import annotations

from .backend import RealBackend

__all__ = ["RealBackend"]
