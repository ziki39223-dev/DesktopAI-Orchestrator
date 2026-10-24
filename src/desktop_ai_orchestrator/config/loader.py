"""``config.yaml`` 加载：合并顺序 + 环境变量覆盖 + 路径解析。

不做业务校验之外的推断，加载失败一律抛 ``ConfigError``（由入口转成启动失败）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ..contracts.errors import ErrorCode, ToolError
from .settings import AppSettings

#: 允许用环境变量覆盖的键（仅这几个，避免环境变量成为隐形契约）。
ENV_OVERRIDES: dict[str, tuple[str, ...]] = {
    "DAO_MODE": ("mode",),
    "DAO_TRANSPORT": ("transport",),
    "DAO_HOST": ("server", "host"),
    "DAO_PORT": ("server", "port"),
    "DAO_AUTH_TOKEN": ("server", "auth_token"),
    "DAO_LOG_LEVEL": ("server", "log_level"),
    "DAO_WINDOW_RULES": ("window_rules_path",),
}

#: 项目内默认配置模板路径（相对仓库根或安装根）。
_DEFAULT_CANDIDATES = ("config/config.yaml", "config.yaml")


def resolve_config_path(explicit: str | Path | None = None) -> Path:
    """确定实际使用的配置文件路径。

    顺序：显式参数 > ``config/config.yaml`` > ``config.yaml``。
    """
    if explicit is not None:
        path = Path(explicit)
        if not path.is_file():
            raise ToolError(
                ErrorCode.RULES_INVALID,
                f"配置文件不存在：{path}",
                detail={"path": str(path)},
            )
        return path

    for candidate in _DEFAULT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path

    raise ToolError(
        ErrorCode.RULES_INVALID,
        "找不到配置文件，请提供 --config 或创建 config/config.yaml",
        detail={"searched": list(_DEFAULT_CANDIDATES)},
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolError(
            ErrorCode.RULES_INVALID,
            f"配置文件 YAML 语法错误：{path}",
            detail={"path": str(path), "reason": str(exc)},
        ) from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ToolError(
            ErrorCode.RULES_INVALID,
            f"配置文件顶层必须是映射结构：{path}",
            detail={"path": str(path), "actual_type": type(raw).__name__},
        )
    return raw


def _ensure_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    child = parent.get(key)
    if child is None:
        child = {}
        parent[key] = child
    if not isinstance(child, dict):
        raise ToolError(
            ErrorCode.RULES_INVALID,
            f"配置节 ``{key}`` 必须是映射结构",
            detail={"key": key, "actual_type": type(child).__name__},
        )
    return child


def _apply_env_overrides(document: dict[str, Any], environ: dict[str, str]) -> None:
    """把环境变量写入（可能是嵌套的）配置字典。"""
    for env_key, path in ENV_OVERRIDES.items():
        value = environ.get(env_key)
        if value is None or value == "":
            continue
        node = document
        for part in path[:-1]:
            node = _ensure_mapping(node, part)
        leaf = path[-1]
        if leaf == "port":
            try:
                node[leaf] = int(value)
            except ValueError as exc:
                raise ToolError(
                    ErrorCode.RULES_INVALID,
                    f"环境变量 {env_key} 必须是整数",
                    detail={"value": value},
                ) from exc
        else:
            node[leaf] = value


def load_settings(
    config_path: str | Path | None = None,
    *,
    environ: dict[str, str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> AppSettings:
    """加载配置并返回校验通过的 ``AppSettings``。

    Args:
        config_path: 显式配置文件路径；为空则按 :func:`resolve_config_path` 搜索。
        environ: 环境变量映射，默认 ``os.environ``（测试可注入）。
        overrides: 最高优先级的运行时覆盖（如 CLI 参数 ``--mode``）。
    """
    path = resolve_config_path(config_path)
    document = _read_yaml(path)

    # 相对路径按配置文件所在目录的父目录（即项目根）解析，保证从任意 cwd 启动都正确。
    project_root = path.resolve().parent.parent

    local_path = path.parent / "config.local.yaml"
    if local_path.is_file():
        document = _deep_merge(document, _read_yaml(local_path))

    _apply_env_overrides(document, environ if environ is not None else dict(os.environ))

    if overrides:
        document = _deep_merge(document, overrides)

    try:
        settings = AppSettings.model_validate(document)
    except Exception as exc:  # pydantic.ValidationError 在此统一转结构化错误
        raise ToolError(
            ErrorCode.RULES_INVALID,
            "config.yaml 校验失败",
            detail={"path": str(path), "reason": str(exc)},
        ) from exc

    return settings.model_copy(
        update={
            "config_dir": _absolute(settings.config_dir, project_root),
            "window_rules_path": _absolute(settings.window_rules_path, project_root),
            "log_dir": _absolute(settings.log_dir, project_root) if settings.log_dir else None,
        }
    )


def _absolute(path: Path, project_root: Path) -> Path:
    return path if path.is_absolute() else (project_root / path).resolve()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并，``override`` 优先；不修改入参。"""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
