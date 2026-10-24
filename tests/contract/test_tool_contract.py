"""契约测试：四个工具的入参/出参结构，Mock 与 Real（Fake 驱动）双跑。

纪律（docs/04-dev-rules.md §6）：契约测试对两后端参数化，任何字段差异都算失败。
"""

from __future__ import annotations

from typing import Any

import pytest

from desktop_ai_orchestrator.backends.mock import MockBackend
from desktop_ai_orchestrator.backends.real import RealBackend
from desktop_ai_orchestrator.config.rules import load_window_rules
from desktop_ai_orchestrator.config.settings import MockSettings, RealSettings
from desktop_ai_orchestrator.contracts.constants import COMPLETION_MARKER, FetchStatus
from desktop_ai_orchestrator.contracts.errors import ErrorCode

from ..fakes import FakeControl, FakeDriver, FakeWindow

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


# --------------------------------------------------------------------------- #
# 后端工厂
# --------------------------------------------------------------------------- #


def _fake_window(win_key: str = "trae") -> FakeWindow:
    return FakeWindow(
        win_key=win_key,
        hwnd=0x2000,
        title=f"{win_key.title()} - 工作区",
        input=FakeControl(),
        output=FakeControl(),
        send=FakeControl(),
    )


@pytest.fixture(params=["mock", "real"])
def backend(request: pytest.FixtureRequest, rules_file: Any) -> Any:
    """同一套断言跑两个后端。"""
    rules = load_window_rules(rules_file)
    if request.param == "mock":
        return MockBackend(rules=rules, settings=MockSettings(), rules_path=str(rules_file))
    return RealBackend(
        rules=rules,
        driver=FakeDriver(windows={"trae": _fake_window()}),
        settings=RealSettings(
            locate_attempts=1, locate_delay_s=0.0, poll_interval_s=0.0, send_confirm_s=0.0
        ),
        rules_path=str(rules_file),
    )


# --------------------------------------------------------------------------- #
# 1. list_target_windows
# --------------------------------------------------------------------------- #


def test_list_target_windows_contract(backend: Any) -> None:
    data = backend.list_target_windows(include_unavailable=False)
    assert data.windows, "至少应返回一个客户端"

    item = data.windows[0].model_dump()
    assert {"win_key", "display_name", "matched", "hwnd", "title", "class_name", "pid",
            "ready", "notes"} <= set(item)
    assert item["win_key"] in {"trae", "qoder", "workbuddy"}
    assert item["matched"] is True
    assert item["ready"] is True


def test_list_target_windows_include_unavailable_returns_all(backend: Any) -> None:
    data = backend.list_target_windows(include_unavailable=True)
    keys = [window.win_key for window in data.windows]
    assert set(keys) == {"trae", "qoder", "workbuddy"}


# --------------------------------------------------------------------------- #
# 2. send_prompt
# --------------------------------------------------------------------------- #


def test_send_prompt_appends_marker(backend: Any) -> None:
    outcome = backend.send_prompt(win_key="trae", prompt="请给出开题大纲", append_marker=True)
    data = outcome.data

    assert data.sent is True
    assert data.win_key == "trae"
    assert data.prompt_length > len("请给出开题大纲")
    assert data.sent_at.tzinfo is not None
    assert outcome.turn_id


def test_send_prompt_preview_is_short(backend: Any) -> None:
    long_prompt = "很长的正文" * 100
    data = backend.send_prompt(win_key="trae", prompt=long_prompt).data
    assert len(data.prompt_preview) <= 41
    assert data.prompt_length > len(long_prompt)


def test_send_prompt_real_writes_to_input_control(rules_file: Any) -> None:
    window = _fake_window()
    driver = FakeDriver(windows={"trae": window})
    backend = RealBackend(
        rules=load_window_rules(rules_file),
        driver=driver,
        settings=RealSettings(locate_attempts=1, locate_delay_s=0.0, send_confirm_s=0.0),
        rules_path=str(rules_file),
    )

    backend.send_prompt(win_key="trae", prompt="正文")

    assert window.input is not None
    assert COMPLETION_MARKER in window.input.text
    assert driver.send_count == 1


# --------------------------------------------------------------------------- #
# 3. fetch_output
# --------------------------------------------------------------------------- #


def test_fetch_output_completed_when_marker_present(backend: Any) -> None:
    backend.send_prompt(win_key="trae", prompt="问题")
    data = backend.fetch_output(win_key="trae", timeout_s=1.0)

    assert data.status is FetchStatus.COMPLETED
    assert data.completed is True
    assert data.marker_found is True
    assert COMPLETION_MARKER in data.text
    assert data.text_length == len(data.text)


def test_fetch_output_generating_is_not_error(rules_file: Any) -> None:
    backend = MockBackend(
        rules=load_window_rules(rules_file),
        settings=MockSettings(generating_polls=2),
        rules_path=str(rules_file),
    )
    backend.send_prompt(win_key="trae", prompt="问题")

    first = backend.fetch_output(win_key="trae", timeout_s=1.0)
    assert first.status is FetchStatus.GENERATING
    assert first.completed is False
    assert first.marker_found is False

    backend.fetch_output(win_key="trae", timeout_s=1.0)
    third = backend.fetch_output(win_key="trae", timeout_s=1.0)
    assert third.status is FetchStatus.COMPLETED


def test_fetch_output_timeout_when_marker_never_appears(rules_file: Any) -> None:
    driver = FakeDriver(
        windows={"trae": _fake_window()},
        output_script=["正在思考，无结束标记"],
    )
    backend = RealBackend(
        rules=load_window_rules(rules_file),
        driver=driver,
        settings=RealSettings(locate_attempts=1, locate_delay_s=0.0, poll_interval_s=0.0),
        rules_path=str(rules_file),
    )

    data = backend.fetch_output(win_key="trae", timeout_s=0.05)
    assert data.status is FetchStatus.TIMEOUT
    assert data.completed is False
    assert data.text


def test_fetch_output_truncates_by_max_chars(rules_file: Any) -> None:
    long_text = "长文本" * 200 + COMPLETION_MARKER
    driver = FakeDriver(windows={"trae": _fake_window()}, output_script=[long_text])
    backend = RealBackend(
        rules=load_window_rules(rules_file),
        driver=driver,
        settings=RealSettings(locate_attempts=1, locate_delay_s=0.0, poll_interval_s=0.0),
        rules_path=str(rules_file),
    )

    data = backend.fetch_output(win_key="trae", timeout_s=0.1, max_chars=50)
    assert data.truncated is True
    assert data.text_length == 50


# --------------------------------------------------------------------------- #
# 4. reload_window_rules
# --------------------------------------------------------------------------- #


def test_reload_window_rules_contract(backend: Any, rules_file: Any) -> None:
    data = backend.reload_window_rules(path=str(rules_file))
    assert data.loaded is True
    assert data.path == str(rules_file)
    assert data.rules_version == "test-1.0"
    assert set(data.clients) == {"trae", "qoder", "workbuddy"}


# --------------------------------------------------------------------------- #
# 错误码契约
# --------------------------------------------------------------------------- #


def test_unknown_win_key_raises_window_not_found(rules_file: Any) -> None:
    backend = MockBackend(rules=load_window_rules(rules_file), rules_path=str(rules_file))
    from desktop_ai_orchestrator.contracts.errors import ToolError

    with pytest.raises(ToolError) as excinfo:
        backend.send_prompt(win_key="unknown", prompt="x")
    assert excinfo.value.code is ErrorCode.WINDOW_NOT_FOUND


def test_real_missing_window_raises_window_not_found(rules_file: Any) -> None:
    from desktop_ai_orchestrator.contracts.errors import ToolError

    backend = RealBackend(
        rules=load_window_rules(rules_file),
        driver=FakeDriver(windows={}),
        settings=RealSettings(locate_attempts=1, locate_delay_s=0.0),
        rules_path=str(rules_file),
    )
    with pytest.raises(ToolError) as excinfo:
        backend.send_prompt(win_key="trae", prompt="x")
    assert excinfo.value.code is ErrorCode.WINDOW_NOT_FOUND


def test_real_missing_control_raises_control_not_found(rules_file: Any) -> None:
    from desktop_ai_orchestrator.contracts.errors import ToolError

    window = _fake_window()
    window.input = None  # 模拟采集失效
    backend = RealBackend(
        rules=load_window_rules(rules_file),
        driver=FakeDriver(windows={"trae": window}),
        settings=RealSettings(locate_attempts=1, locate_delay_s=0.0),
        rules_path=str(rules_file),
    )
    with pytest.raises(ToolError) as excinfo:
        backend.send_prompt(win_key="trae", prompt="x")
    assert excinfo.value.code is ErrorCode.CONTROL_NOT_FOUND
    assert excinfo.value.detail["field"] == "input"
