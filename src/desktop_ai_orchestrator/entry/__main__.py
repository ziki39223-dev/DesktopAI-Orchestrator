"""支持 ``python -m desktop_ai_orchestrator.entry [sse|stdio]``。

不带子命令时默认 SSE。
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
