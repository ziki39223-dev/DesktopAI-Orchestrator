"""端到端测试：真起 stdio 子进程，用 MCP 客户端调四个工具。

验证点：
1. 工具清单与契约文档一致（名字、必填参数）；
2. 调用返回结构符合信封契约；
3. mock 模式下 send_prompt → fetch_output 闭环可用；
4. stdout 不被日志污染（stdio 传输的硬要求）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"

EXPECTED_TOOLS = {"list_target_windows", "send_prompt", "fetch_output", "reload_window_rules"}


def _server_params(rules_file: Path, tmp_path: Path) -> StdioServerParameters:
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC),
        "PYTHONIOENCODING": "utf-8",
        "DAO_MODE": "mock",
        "DAO_LOG_LEVEL": "WARNING",
    }
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "desktop_ai_orchestrator.entry",
            "stdio",
            "--config",
            str(PROJECT_ROOT / "config" / "config.yaml"),
            "--window-rules",
            str(rules_file),
            "--log-dir",
            "",
        ],
        env=env,
        cwd=str(PROJECT_ROOT),
    )


def _payload(result: Any) -> dict[str, Any]:
    """把 CallToolResult 还原成出参 dict（优先 structured）。"""
    if getattr(result, "structuredContent", None):
        content = result.structuredContent
        # FastMCP 会把返回 dict 包在 result 键下
        if isinstance(content, dict) and set(content) == {"result"}:
            return content["result"]  # type: ignore[no-any-return]
        return content  # type: ignore[no-any-return]

    for item in result.content or []:
        text = getattr(item, "text", None)
        if text:
            return json.loads(text)  # type: ignore[no-any-return]
    raise AssertionError("MCP 调用没有返回内容")


@pytest.mark.anyio
async def test_stdio_lists_four_tools(rules_file: Path, tmp_path: Path) -> None:
    # 刻意保留嵌套 async with：stdio_client 的上下文必须比 ClientSession 长，
    # 合并成单条 with 会让退出顺序依赖实现细节。
    async with stdio_client(_server_params(rules_file, tmp_path)) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

    names = {tool.name for tool in tools.tools}
    assert names >= EXPECTED_TOOLS

    send_tool = next(tool for tool in tools.tools if tool.name == "send_prompt")
    # mcp 2.x 用 input_schema，1.x 用 inputSchema，这里两种都兼容。
    schema = getattr(send_tool, "input_schema", None) or send_tool.inputSchema
    assert "win_key" in schema["properties"]
    assert "prompt" in schema["properties"]
    assert set(schema.get("required", [])) == {"win_key", "prompt"}


@pytest.mark.anyio
async def test_stdio_full_flow_mock(rules_file: Path, tmp_path: Path) -> None:
    # 嵌套 async with 的理由同上：保证 stdio 客户端在会话之后退出。
    async with stdio_client(_server_params(rules_file, tmp_path)) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = _payload(await session.call_tool("list_target_windows", {}))
            assert listed["ok"] is True
            assert listed["backend"] == "mock"
            assert listed["data"]["windows"]
            win_key = listed["data"]["windows"][0]["win_key"]

            sent = _payload(
                await session.call_tool(
                    "send_prompt", {"win_key": win_key, "prompt": "给我一份开题报告大纲"}
                )
            )
            assert sent["ok"] is True
            assert sent["data"]["sent"] is True

            fetched = _payload(
                await session.call_tool("fetch_output", {"win_key": win_key, "timeout_s": 5})
            )
            assert fetched["ok"] is True
            assert fetched["data"]["status"] == "completed"
            assert fetched["data"]["completed"] is True
            assert "【Agent任务完成】" in fetched["data"]["text"]


@pytest.mark.anyio
async def test_stdio_invalid_argument_is_structured(rules_file: Path, tmp_path: Path) -> None:
    async with stdio_client(_server_params(rules_file, tmp_path)) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = _payload(
                await session.call_tool("send_prompt", {"win_key": "not-a-client", "prompt": "x"})
            )

    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"
    assert result["data"] is None
    assert result["error"]["detail"]["fields"]
