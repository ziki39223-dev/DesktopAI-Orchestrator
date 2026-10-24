"""配置层：加载并校验 ``config.yaml`` 与 ``window_rules.json``。

约束：本层只产出不可变配置对象，不持有后端实例、不做业务判断。
"""

from __future__ import annotations

from .loader import load_settings, resolve_config_path
from .rules import WindowRules, load_window_rules, parse_window_rules
from .settings import AppSettings, ServerSettings, TransportKind

__all__ = [
    "AppSettings",
    "ServerSettings",
    "TransportKind",
    "WindowRules",
    "load_settings",
    "load_window_rules",
    "parse_window_rules",
    "resolve_config_path",
]
