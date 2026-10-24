"""MCP Server 装配：注册四个工具、配置生命周期。

设计要点：
- 工具函数只做「原始入参 → pydantic 校验 → ToolService → dict」，不做业务；
- 入参校验失败统一映射为 ``INVALID_ARGUMENT``，不让客户端看到 pydantic 原始报错；
- 出参直接返回契约模型的 ``model_dump``，字段与 docs/06 一致，两模式无差异。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from ..config.settings import AppSettings
from ..contracts.tools import (
    FetchOutputRequest,
    ListTargetWindowsRequest,
    ReloadWindowRulesRequest,
    SendPromptRequest,
)
from ..observability.logging import configure_logging
from ..tools.service import ToolService, build_service

_log = logging.getLogger("dao.server")

SERVER_NAME = "desktop-ai-orchestrator"
SERVER_VERSION = "0.1.0"
SERVER_INSTRUCTIONS = (
    "桌面 AI 调度 MCP 服务：向本机 Trae / Qoder / WorkBuddy 客户端下发 prompt 并取回结果。\n"
    "典型流程：list_target_windows → send_prompt → 循环 fetch_output 直到 status=completed。\n"
    "fetch_output 返回 status=generating / timeout / idle 属于正常状态（ok=true），"
    "继续轮询即可，不要当失败处理。"
)


def register_tools(server: MCPServer, service: ToolService) -> None:
    """把四个工具注册到 MCP Server。"""

    @server.tool(
        name="list_target_windows",
        description="列出当前可识别的 Trae / Qoder / WorkBuddy 窗口及其可用状态",
    )
    def list_target_windows(include_unavailable: bool = False) -> dict[str, Any]:
        """列出目标客户端窗口。

        Args:
            include_unavailable: 是否包含未启动或控件未就绪的客户端（默认 False）。
        """
        try:
            request = ListTargetWindowsRequest(include_unavailable=include_unavailable)
        except ValidationError as exc:
            return service.invalid("list_target_windows", exc)
        return service.list_target_windows(request).model_dump(mode="json")

    @server.tool(
        name="send_prompt",
        description="向指定客户端窗口写入 prompt 并触发发送；默认自动追加结束标记约定",
    )
    def send_prompt(win_key: str, prompt: str, append_marker: bool = True) -> dict[str, Any]:
        """向目标窗口下发 prompt。

        Args:
            win_key: 客户端标识，取值 trae / qoder / workbuddy。
            prompt: 要发送的正文。
            append_marker: 是否由服务端自动追加结束标记约定（默认 True）。
        """
        try:
            request = SendPromptRequest(
                win_key=win_key,  # type: ignore[arg-type]
                prompt=prompt,
                append_marker=append_marker,
            )
        except ValidationError as exc:
            return service.invalid("send_prompt", exc)
        return service.send_prompt(request).model_dump(mode="json")

    @server.tool(
        name="fetch_output",
        description="读取聊天区最新输出并检测结束标记；status 非 completed 时继续轮询即可",
    )
    def fetch_output(
        win_key: str,
        timeout_s: float = 30.0,
        since_last_send: bool = True,
        max_chars: int = 20_000,
    ) -> dict[str, Any]:
        """读取目标窗口输出。

        Args:
            win_key: 客户端标识，取值 trae / qoder / workbuddy。
            timeout_s: 单次调用最长等待秒数（默认 30，上限 300）。
            since_last_send: 只取上一次 send_prompt 之后的新增内容（默认 True）。
            max_chars: 返回文本的最大字符数。
        """
        try:
            request = FetchOutputRequest(
                win_key=win_key,  # type: ignore[arg-type]
                timeout_s=timeout_s,
                since_last_send=since_last_send,
                max_chars=max_chars,
            )
        except ValidationError as exc:
            return service.invalid("fetch_output", exc)
        return service.fetch_output(request).model_dump(mode="json")

    @server.tool(
        name="reload_window_rules",
        description="重载控件规则 window_rules.json，适配客户端版本更新，无需重启服务",
    )
    def reload_window_rules(path: str | None = None) -> dict[str, Any]:
        """重载控件规则。

        Args:
            path: 规则文件路径；为空则重载默认 config/window_rules.json。
        """
        try:
            request = ReloadWindowRulesRequest(path=path)
        except ValidationError as exc:
            return service.invalid("reload_window_rules", exc)
        return service.reload_window_rules(request).model_dump(mode="json")


@asynccontextmanager
async def server_lifespan(_server: MCPServer) -> AsyncIterator[None]:
    """进程级生命周期：启动/退出日志。"""
    _log.info("MCP Server 启动：%s", SERVER_NAME)
    try:
        yield
    finally:
        _log.info("MCP Server 退出：%s", SERVER_NAME)


def build_server(settings: AppSettings) -> MCPServer:
    """按配置构建可运行的 MCP Server（尚未启动传输）。"""
    configure_logging(
        level=settings.server.log_level,
        log_dir=settings.log_dir,
        force=True,
    )

    service = build_service(settings)
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=server_lifespan,
    )
    register_tools(server, service)
    _log.info(
        "装配完成：mode=%s transport=%s rules=%s",
        settings.mode.value,
        settings.transport.value,
        settings.window_rules_path,
    )
    return server
