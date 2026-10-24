"""单元测试：文本处理与关联 ID。"""

from __future__ import annotations

import pytest

from desktop_ai_orchestrator.common.ids import new_correlation_id
from desktop_ai_orchestrator.common.text import (
    now_local,
    preview,
    strip_completion_marker,
    truncate,
)
from desktop_ai_orchestrator.contracts.constants import COMPLETION_MARKER


def test_preview_collapses_whitespace_and_truncates() -> None:
    text = "第一行\n\n第二行\t第三行" + "填充" * 50
    result = preview(text, limit=10)
    assert "\n" not in result
    assert result.endswith("…")
    assert len(result) == 11


def test_preview_keeps_short_text_intact() -> None:
    assert preview("短文本") == "短文本"


def test_truncate_reports_flag() -> None:
    text, cut = truncate("abcdef", 3)
    assert (text, cut) == ("abc", True)

    text, cut = truncate("abc", 10)
    assert (text, cut) == ("abc", False)


def test_strip_completion_marker_only_tail() -> None:
    body = "回答正文"
    assert strip_completion_marker(f"{body}\n{COMPLETION_MARKER}") == body
    # 标记在中间时不应被删
    mid = f"{COMPLETION_MARKER} 中间出现"
    assert strip_completion_marker(mid) == mid


def test_now_local_has_timezone() -> None:
    assert now_local().tzinfo is not None


def test_correlation_id_unique() -> None:
    ids = {new_correlation_id() for _ in range(200)}
    assert len(ids) == 200


@pytest.mark.parametrize("prefix", ["c", "tool"])
def test_correlation_id_prefix(prefix: str) -> None:
    assert new_correlation_id(prefix).startswith(f"{prefix}-")
