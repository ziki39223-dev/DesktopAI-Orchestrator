"""测试公共夹具：配置、规则、Fake 驱动。

所有夹具都在 Mock 模式或 Fake 驱动下工作，不依赖任何 Windows GUI。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from desktop_ai_orchestrator.config.settings import (
    AppSettings,
    MockSettings,
    RealSettings,
    ServerSettings,
)
from desktop_ai_orchestrator.contracts.constants import COMPLETION_MARKER

RULES_DOCUMENT: dict[str, Any] = {
    "rules_version": "test-1.0",
    "clients": {
        win_key: {
            "display_name": display,
            "title_keywords": [display],
            "class_name": "Chrome_WidgetWin_1",
            "input": [
                {"type": "automation_id", "value": "input"},
                {"type": "control_type", "value": "edit", "index": 0},
            ],
            "send": [{"type": "accelerator", "value": "{ENTER}"}],
            "output": [{"type": "automation_id", "value": "output"}],
            "completion_marker": COMPLETION_MARKER,
        }
        for win_key, display in (
            ("trae", "Trae"),
            ("qoder", "Qoder"),
            ("workbuddy", "WorkBuddy"),
        )
    },
}


@pytest.fixture
def rules_document() -> dict[str, Any]:
    return json.loads(json.dumps(RULES_DOCUMENT))


@pytest.fixture
def rules_file(tmp_path: Path, rules_document: dict[str, Any]) -> Path:
    path = tmp_path / "window_rules.json"
    path.write_text(json.dumps(rules_document, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def mock_settings(tmp_path: Path, rules_file: Path) -> AppSettings:
    """Mock 模式配置，日志不落盘。"""
    return AppSettings(
        mode="mock",  # type: ignore[arg-type]
        transport="stdio",  # type: ignore[arg-type]
        window_rules_path=rules_file,
        log_dir=None,
        server=ServerSettings(log_level="WARNING"),
        mock=MockSettings(),
    )


@pytest.fixture
def real_settings_offline(tmp_path: Path, rules_file: Path) -> AppSettings:
    """Real 模式配置但驱动由测试注入，等待时间压到最小。"""
    return AppSettings(
        mode="real",  # type: ignore[arg-type]
        transport="stdio",  # type: ignore[arg-type]
        window_rules_path=rules_file,
        log_dir=None,
        server=ServerSettings(log_level="WARNING"),
        real=RealSettings(locate_attempts=2, locate_delay_s=0.0, poll_interval_s=0.0, send_confirm_s=0.0),
    )
