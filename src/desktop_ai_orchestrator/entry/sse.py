"""SSE 服务入口。

    python -m desktop_ai_orchestrator.entry.sse
    python -m desktop_ai_orchestrator.entry.sse --port 8765 --mode mock
"""

from __future__ import annotations

import sys

from .cli import run_sse

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_sse(sys.argv[1:]))
