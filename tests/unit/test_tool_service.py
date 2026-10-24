"""工具服务层测试：信封结构、错误映射、日志脱敏口径、双后端 backend 字段。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from desktop_ai_orchestrator.backends.mock import MockBackend
from desktop_ai_orchestrator.backends.real import RealBackend
from desktop_ai_orchestrator.config.rules import load_window_rules
from desktop_ai_orchestrator.config.settings import AppSettings, MockSettings
from desktop_ai_orchestrator.contracts.constants import BackendKind, FetchStatus
from desktop_ai_orchestrator.contracts.errors import ErrorCode
from desktop_ai_orchestrator.contracts.tools import (
    FetchOutputRequest,
    ListTargetWindowsRequest,
    ReloadWindowRulesRequest,
    SendPromptRequest,
)
from desktop_ai_orchestrator.routers.backend_router import BackendRouter
from desktop_ai_orchestrator.tools.service import ToolService

from ..fakes import FakeDriver, FakeWindow

ENVELOPE_KEYS = {
    "ok",
    "error_code",
    "message",
    "backend",
    "correlation_id",
    "elapsed_ms",
    "error",
    "data",
}


@pytest.fixture
def service(mock_settings: AppSettings) -> ToolService:
    return ToolService(BackendRouter(mock_settings))


@pytest.fixture
def real_service(real_settings_offline: AppSettings, rules_file: Path) -> ToolService:
    """real 模式 + Fake 驱动，用于验证 backend 字段与实机分支。"""
    router = BackendRouter(
        real_settings_offline,
        backend=RealBackend(
            rules=load_window_rules(rules_file),
            driver=FakeDriver(windows={"trae": FakeWindow("trae", 0x3000, "Trae - 工作区")}),
            settings=real_settings_offline.real,
            rules_path=str(rules_file),
        ),
    )
    return ToolService(router)


# --------------------------------------------------------------------------- #
# 信封结构
# --------------------------------------------------------------------------- #


def test_envelope_has_all_fields(service: ToolService) -> None:
    payload = service.list_target_windows(ListTargetWindowsRequest()).model_dump(mode="json")
    assert set(payload) == ENVELOPE_KEYS
    assert payload["ok"] is True
    assert payload["error_code"] == ErrorCode.OK.value
    assert payload["backend"] == BackendKind.MOCK.value
    assert payload["correlation_id"]
    assert isinstance(payload["elapsed_ms"], int)
    assert payload["error"] is None


def test_correlation_id_differs_per_call(service: ToolService) -> None:
    assert service.list_target_windows().correlation_id != service.list_target_windows().correlation_id


def test_backend_field_reflects_mode(real_service: ToolService) -> None:
    envelope = real_service.list_target_windows()
    assert envelope.backend is BackendKind.REAL
    assert envelope.data is not None
    assert [window.win_key for window in envelope.data.windows] == ["trae"]


# --------------------------------------------------------------------------- #
# 闭环
# --------------------------------------------------------------------------- #


def test_send_then_fetch_full_flow(service: ToolService) -> None:
    send = service.send_prompt(SendPromptRequest(win_key="trae", prompt="梳理开题大纲"))
    assert send.ok is True
    assert send.data is not None
    assert send.data.sent is True

    fetch = service.fetch_output(FetchOutputRequest(win_key="trae", timeout_s=1.0))
    assert fetch.ok is True
    assert fetch.data is not None
    assert fetch.data.status is FetchStatus.COMPLETED
    assert fetch.data.completed is True


def test_generating_status_is_ok_envelope(rules_file: Path, mock_settings: AppSettings) -> None:
    """generating 必须仍是 ok=True（ADR-005：未完成不是错误）。"""
    settings = mock_settings.model_copy(update={"mock": MockSettings(generating_polls=1)})
    service = ToolService(BackendRouter(settings))
    service.send_prompt(SendPromptRequest(win_key="trae", prompt="问题"))

    envelope = service.fetch_output(FetchOutputRequest(win_key="trae", timeout_s=1.0))
    assert envelope.ok is True
    assert envelope.error_code is ErrorCode.OK
    assert envelope.data is not None
    assert envelope.data.status is FetchStatus.GENERATING


# --------------------------------------------------------------------------- #
# 错误映射
# --------------------------------------------------------------------------- #


def test_injected_error_maps_to_envelope(mock_settings: AppSettings) -> None:
    settings = mock_settings.model_copy(
        update={"mock": MockSettings(inject_errors={"trae:send": "SEND_FAILED"})}
    )
    service = ToolService(BackendRouter(settings))

    envelope = service.send_prompt(SendPromptRequest(win_key="trae", prompt="x"))

    assert envelope.ok is False
    assert envelope.error_code is ErrorCode.SEND_FAILED
    assert envelope.data is None
    assert envelope.error is not None
    assert envelope.error.code is ErrorCode.SEND_FAILED


def test_invalid_argument_mapping(service: ToolService) -> None:
    with pytest.raises(ValidationError) as excinfo:
        SendPromptRequest(win_key="trae", prompt="   ")

    payload = service.invalid("send_prompt", excinfo.value)
    assert payload["ok"] is False
    assert payload["error_code"] == ErrorCode.INVALID_ARGUMENT.value
    assert payload["data"] is None
    assert payload["error"]["detail"]["fields"]


def test_internal_error_is_wrapped(service: ToolService) -> None:
    """未预期异常必须被兜底成 INTERNAL_ERROR，不能让裸异常冒到 MCP 层。"""

    def boom() -> None:
        raise RuntimeError("模拟未预期错误")

    envelope = service._run("boom", {}, boom)
    assert envelope.ok is False
    assert envelope.error_code is ErrorCode.INTERNAL_ERROR
    assert envelope.data is None
    assert envelope.error is not None
    assert "RuntimeError" in envelope.error.message


def test_reload_rules_invalid_path(service: ToolService) -> None:
    envelope = service.reload_window_rules(ReloadWindowRulesRequest(path="不存在.json"))
    assert envelope.ok is False
    assert envelope.error_code is ErrorCode.RULES_INVALID


# --------------------------------------------------------------------------- #
# 其余
# --------------------------------------------------------------------------- #


def test_reload_rules_tool(service: ToolService, rules_file: Path) -> None:
    envelope = service.reload_window_rules(ReloadWindowRulesRequest(path=str(rules_file)))
    assert envelope.ok is True
    assert envelope.data is not None
    assert envelope.data.loaded is True
    assert set(envelope.data.clients) == {"trae", "qoder", "workbuddy"}


def test_prompt_preview_not_full_text(service: ToolService) -> None:
    """日志与出参里的摘要不得包含完整正文（脱敏口径）。"""
    secret = "机密内容" * 50
    send = service.send_prompt(SendPromptRequest(win_key="trae", prompt=secret))
    assert send.data is not None
    assert secret not in send.data.prompt_preview
    assert send.data.prompt_length > len(secret)


def test_mock_backend_settings_not_shared() -> None:
    """MockSettings 默认值不应被跨实例共享（避免注入污染）。"""
    first = MockSettings()
    second = MockSettings()
    first.inject_errors["trae"] = "SEND_FAILED"
    assert second.inject_errors == {}


def test_mock_backend_kind(rules_file: Path) -> None:
    backend = MockBackend(rules=load_window_rules(rules_file), rules_path=str(rules_file))
    assert backend.kind is BackendKind.MOCK
