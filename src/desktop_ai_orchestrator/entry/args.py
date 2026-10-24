"""命令行参数解析：两个入口（sse / stdio）共用，只做参数收集不做业务。

配置合并优先级（高 → 低）：
命令行显式参数 > 环境变量 > ``config.local.yaml`` > ``config/config.yaml`` > 内置默认。
"""

from __future__ import annotations

import argparse
from typing import Any

from ..config.settings import TransportKind


def build_parser(transport_default: TransportKind) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desktop-ai-orchestrator",
        description="桌面 AI 调度 MCP 服务（Trae / Qoder / WorkBuddy）",
    )
    parser.add_argument("-c", "--config", default=None, help="配置文件路径，默认 config/config.yaml")
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default=None,
        help="强制后端模式，覆盖配置文件的 mode",
    )
    parser.add_argument("--host", default=None, help="SSE 监听地址，覆盖配置")
    parser.add_argument("--port", type=int, default=None, help="SSE 监听端口，覆盖配置")
    parser.add_argument("--window-rules", default=None, help="window_rules.json 路径，覆盖配置")
    parser.add_argument(
        "--log-dir",
        default=None,
        help="日志目录；传空字符串表示不落文件",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="只打印最终生效配置并退出（排障用）",
    )
    return parser


def overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """把命令行显式给出的值转成配置覆盖字典（未给出的不覆盖）。"""
    overrides: dict[str, Any] = {}

    if args.mode:
        overrides["mode"] = args.mode
    if args.window_rules:
        overrides["window_rules_path"] = args.window_rules
    if args.log_dir is not None:
        overrides["log_dir"] = args.log_dir or None

    server: dict[str, Any] = {}
    if args.host:
        server["host"] = args.host
    if args.port:
        server["port"] = args.port
    if server:
        overrides["server"] = server

    return overrides
