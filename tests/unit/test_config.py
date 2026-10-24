"""配置层测试：加载优先级、环境变量覆盖、规则校验错误码。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desktop_ai_orchestrator.config.loader import load_settings, resolve_config_path
from desktop_ai_orchestrator.config.rules import load_window_rules, parse_window_rules
from desktop_ai_orchestrator.contracts.constants import BackendKind
from desktop_ai_orchestrator.contracts.errors import ErrorCode, ToolError


def _write_config(tmp_path: Path, document: str) -> Path:
    path = tmp_path / "config" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path


def test_load_settings_defaults(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: mock\n")
    settings = load_settings(path, environ={})
    assert settings.mode is BackendKind.MOCK
    assert settings.server.port == 8765
    assert settings.window_rules_path.is_absolute()


def test_env_overrides_win(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: mock\nserver:\n  port: 8000\n")
    settings = load_settings(path, environ={"DAO_MODE": "real", "DAO_PORT": "9001"})
    assert settings.mode is BackendKind.REAL
    assert settings.server.port == 9001


def test_cli_overrides_beat_env(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: mock\n")
    settings = load_settings(
        path, environ={"DAO_MODE": "real"}, overrides={"mode": "mock"}
    )
    assert settings.mode is BackendKind.MOCK


def test_local_config_merged(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: mock\nserver:\n  port: 8000\n")
    (path.parent / "config.local.yaml").write_text("server:\n  port: 9002\n", encoding="utf-8")
    settings = load_settings(path, environ={})
    assert settings.server.port == 9002


def test_bad_env_port_reports_rules_invalid(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: mock\n")
    with pytest.raises(ToolError) as excinfo:
        load_settings(path, environ={"DAO_PORT": "abc"})
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_broken_yaml_reports_rules_invalid(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: [unclosed\n")
    with pytest.raises(ToolError) as excinfo:
        load_settings(path, environ={})
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_unknown_mode_rejected(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "mode: hybrid\n")
    with pytest.raises(ToolError) as excinfo:
        load_settings(path, environ={})
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_resolve_config_missing(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as excinfo:
        resolve_config_path(tmp_path / "nope.yaml")
    assert excinfo.value.code is ErrorCode.RULES_INVALID


# --------------------------------------------------------------------------- #
# window_rules
# --------------------------------------------------------------------------- #


def test_rules_require_all_three_clients(rules_document: dict[str, object]) -> None:
    del rules_document["clients"]["qoder"]  # type: ignore[index]
    with pytest.raises(ToolError) as excinfo:
        parse_window_rules(rules_document)
    assert excinfo.value.code is ErrorCode.RULES_INVALID
    assert "qoder" in str(excinfo.value.detail)


def test_rules_reject_unknown_client(rules_document: dict[str, object]) -> None:
    rules_document["clients"]["cursor"] = rules_document["clients"]["trae"]  # type: ignore[index]
    with pytest.raises(ToolError) as excinfo:
        parse_window_rules(rules_document)
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_rules_reject_unknown_field(rules_document: dict[str, object]) -> None:
    rules_document["clients"]["trae"]["intput"] = []  # type: ignore[index]
    with pytest.raises(ToolError) as excinfo:
        parse_window_rules(rules_document)
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_rules_ignore_underscore_comments(rules_document: dict[str, object]) -> None:
    rules_document["_comment"] = "说明性键应被忽略"
    rules_document["clients"]["trae"]["_todo"] = "待采集"  # type: ignore[index]
    rules = parse_window_rules(rules_document)
    assert rules.client_keys == ["trae", "qoder", "workbuddy"]


def test_rules_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as excinfo:
        load_window_rules(tmp_path / "missing.json")
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_rules_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ToolError) as excinfo:
        load_window_rules(path)
    assert excinfo.value.code is ErrorCode.RULES_INVALID


def test_rules_get_unknown_win_key(rules_file: Path) -> None:
    rules = load_window_rules(rules_file)
    with pytest.raises(ToolError) as excinfo:
        rules.get("cursor")
    assert excinfo.value.code is ErrorCode.WINDOW_NOT_FOUND


def test_project_default_rules_loadable() -> None:
    """仓库自带模板必须能被加载，否则工作机首次启动就会失败。"""
    root = Path(__file__).resolve().parents[2]
    rules = load_window_rules(root / "config" / "window_rules.json")
    assert rules.client_keys == ["trae", "qoder", "workbuddy"]
    for key in rules.client_keys:
        target = rules.clients[key]
        assert target.input and target.send and target.output


def test_project_default_config_loadable() -> None:
    root = Path(__file__).resolve().parents[2]
    settings = load_settings(root / "config" / "config.yaml", environ={})
    assert settings.mode is BackendKind.MOCK
    assert settings.window_rules_path.is_file()


def test_rules_template_has_no_placeholder_left_unnoted(rules_document: dict[str, object]) -> None:
    """模板里的示例值必须带 notes 提示，避免工作机直接拿去用。"""
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "config" / "window_rules.json").read_text(encoding="utf-8"))
    for win_key, target in raw["clients"].items():
        for field in ("input", "output"):
            for strategy in target[field]:
                if strategy["type"] == "automation_id":
                    assert strategy.get("notes"), f"{win_key}.{field} 示例值缺 notes 提示"
    assert rules_document is not None
