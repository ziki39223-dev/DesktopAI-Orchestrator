"""命令行联调客户端：不装 Inspector 也能验证四工具。

用法：
    python scripts/mcp_client_demo.py stdio
    python scripts/mcp_client_demo.py sse --url http://127.0.0.1:8765/sse

这是**开发调试脚本**，不属于 MCP 服务的运行依赖。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcp import ClientSession  # noqa: E402
from mcp.client.sse import sse_client  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

WIN_KEYS = ("trae", "qoder", "workbuddy")
MARKER = "【Agent任务完成】"


def _dump(title: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])


def _payload(result: Any) -> dict[str, Any]:
    if getattr(result, "structuredContent", None):
        content = result.structuredContent
        if isinstance(content, dict) and set(content) == {"result"}:
            return content["result"]  # type: ignore[no-any-return]
        return content  # type: ignore[no-any-return]
    for item in result.content or []:
        text = getattr(item, "text", None)
        if text:
            return json.loads(text)  # type: ignore[no-any-return]
    return {}


async def _smoke(session: ClientSession, win_key: str, prompt: str, timeout_s: float) -> int:
    """跑一遍完整流程，返回失败数。"""
    failures = 0

    tools = await session.list_tools()
    _dump("工具清单", {"tools": [tool.name for tool in tools.tools]})

    listed = _payload(await session.call_tool("list_target_windows", {"include_unavailable": True}))
    _dump("list_target_windows", listed)
    if not listed.get("ok"):
        failures += 1

    sent = _payload(await session.call_tool("send_prompt", {"win_key": win_key, "prompt": prompt}))
    _dump("send_prompt", sent)
    if not sent.get("ok"):
        failures += 1
        return failures

    fetched = _payload(
        await session.call_tool("fetch_output", {"win_key": win_key, "timeout_s": timeout_s})
    )
    _dump("fetch_output", fetched)
    status = (fetched.get("data") or {}).get("status")
    print(f"\n[状态] fetch_output → {status}")
    if status != "completed":
        print("[提示] 未完成属正常状态（generating/timeout/idle），编排侧应继续轮询。")

    reloaded = _payload(await session.call_tool("reload_window_rules", {}))
    _dump("reload_window_rules", reloaded)
    if not reloaded.get("ok"):
        failures += 1

    if MARKER in json.dumps(fetched, ensure_ascii=False):
        print("[OK] 已捕获结束标记")
    return failures


async def run_stdio(win_key: str, prompt: str, timeout_s: float) -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "desktop_ai_orchestrator.entry",
            "stdio",
            "--config",
            str(PROJECT_ROOT / "config" / "config.yaml"),
        ],
        cwd=str(PROJECT_ROOT),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return await _smoke(session, win_key, prompt, timeout_s)


async def run_sse(url: str, win_key: str, prompt: str, timeout_s: float) -> int:
    async with sse_client(url) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return await _smoke(session, win_key, prompt, timeout_s)


def main() -> int:
    parser = argparse.ArgumentParser(description="DesktopAI-Orchestrator 联调客户端")
    parser.add_argument("transport", choices=["stdio", "sse"], help="传输方式")
    parser.add_argument("--url", default="http://127.0.0.1:8765/sse", help="SSE 端点")
    parser.add_argument("--win-key", default="trae", choices=list(WIN_KEYS))
    parser.add_argument("--prompt", default="联调测试：请回复一句话，并在结尾输出结束标记")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    if args.transport == "stdio":
        failures = asyncio.run(run_stdio(args.win_key, args.prompt, args.timeout))
    else:
        failures = asyncio.run(run_sse(args.url, args.win_key, args.prompt, args.timeout))

    print("\n[结果]", "全部通过" if failures == 0 else f"{failures} 项失败")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
