"""启动入口：SSE（主推）与 stdio。

用法：
    python -m desktop_ai_orchestrator.entry sse  [--port 8765]
    python -m desktop_ai_orchestrator.entry stdio
或直接：
    python -m desktop_ai_orchestrator.entry.sse
    python -m desktop_ai_orchestrator.entry.stdio
"""

from __future__ import annotations

import argparse
import json
import sys

from ..config.loader import load_settings
from ..config.settings import AppSettings, TransportKind
from ..contracts.errors import ToolError
from ..observability.logging import configure_logging, get_logger
from ..server.app import build_server
from .args import build_parser, overrides_from_args

_log = get_logger("dao.entry")


def _parse(argv: list[str] | None, transport: TransportKind) -> argparse.Namespace:
    parser = build_parser(transport)
    args = parser.parse_args(argv)
    args.transport = transport.value
    return args


def _load(args: argparse.Namespace) -> AppSettings:
    return load_settings(args.config, overrides=overrides_from_args(args))


def _banner(settings: AppSettings) -> None:
    _log.info(
        "DesktopAI-Orchestrator 启动：mode=%s transport=%s rules=%s log_dir=%s",
        settings.mode.value,
        settings.transport.value,
        settings.window_rules_path,
        settings.log_dir,
    )


def run_sse(argv: list[str] | None = None) -> int:
    """启动 SSE 服务（阻塞直到收到退出信号）。"""
    args = _parse(argv, TransportKind.SSE)
    try:
        settings = _load(args)
    except ToolError as exc:
        # 启动期失败直接退出，不做重试：配置错误重试也不会变好。
        print(f"[启动失败] {exc.code.value}: {exc.message}", file=sys.stderr)
        print(json.dumps(exc.detail, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    if args.print_config:
        print(settings.model_dump_json(indent=2))
        return 0

    _banner(settings)
    server = build_server(settings)
    _log.info(
        "SSE 端点：http://%s:%d%s（消息端点：%s）",
        settings.server.host,
        settings.server.port,
        settings.server.sse_path,
        settings.server.message_path,
    )
    if settings.server.auth_token:
        _log.warning("已启用 auth_token：客户端需带 Authorization: Bearer <token>")

    server.run(
        transport="sse",
        host=settings.server.host,
        port=settings.server.port,
        sse_path=settings.server.sse_path,
        message_path=settings.server.message_path,
    )
    return 0


def run_stdio(argv: list[str] | None = None) -> int:
    """启动 stdio 服务（stdout 只走协议，日志一律 stderr / 文件）。"""
    args = _parse(argv, TransportKind.STDIO)
    try:
        settings = _load(args)
    except ToolError as exc:
        # stdio 模式下 stdout 是协议通道，错误只能写 stderr。
        print(f"[启动失败] {exc.code.value}: {exc.message}", file=sys.stderr)
        return 2

    if args.print_config:
        print(settings.model_dump_json(indent=2))
        return 0

    configure_logging(
        level=settings.server.log_level,
        log_dir=settings.log_dir,
        to_stderr=True,
        force=True,
    )
    _banner(settings)
    server = build_server(settings)
    server.run(transport="stdio")
    return 0


def main(argv: list[str] | None = None) -> int:
    """子命令分派：``sse``（默认）/ ``stdio``。"""
    raw = list(sys.argv[1:] if argv is None else argv)
    command = "sse"
    if raw and raw[0] in {"sse", "stdio"}:
        command = raw.pop(0)

    if command == "stdio":
        return run_stdio(raw)
    return run_sse(raw)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
