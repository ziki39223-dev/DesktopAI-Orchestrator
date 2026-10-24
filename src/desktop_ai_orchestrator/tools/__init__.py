"""工具层：四个对外 MCP 工具的纯实现。

纪律（docs/03-directory-layout.md §2）：
- 只做入参校验 → 调后端 → 出参封装 → 错误映射；
- 禁止出现 Windows API、禁止 ``mode == "real"`` 分支；
- 任何异常都必须转成 ``ToolEnvelope(ok=False)``。
"""

from __future__ import annotations

from .service import ToolService, build_service

__all__ = ["ToolService", "build_service"]
