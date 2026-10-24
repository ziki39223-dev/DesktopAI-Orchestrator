"""``window_rules.json`` 模型与加载。

设计要点（docs/07-decision-log.md ADR-006）：
- 控件定位不写死代码，全部外置到规则文件；
- 每个目标给**有序降级链** ``strategies``，按序尝试，全失败才报 CONTROL_NOT_FOUND；
- 规则带 ``rules_version`` 与客户端窗口关键词，便于热重载与版本溯源。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..contracts.constants import COMPLETION_MARKER, WIN_KEYS
from ..contracts.errors import ErrorCode, ToolError

#: 支持的选择器类型。P2 按工作机实测结果继续扩充（只增不删）。
StrategyType = Literal[
    "automation_id",
    "control_type",
    "name",
    "class_name",
    "accelerator",
]


class Strategy(BaseModel):
    """单条控件定位策略。"""

    model_config = ConfigDict(extra="forbid")

    type: StrategyType
    value: str = ""
    #: 同类控件多个时的序号（0 起）。
    index: int | None = Field(default=None, ge=0)
    #: 相对锚点的层级偏移，形如 ``{"up": 2, "down": 1}``，P2 按实测补充语义。
    depth: int | None = Field(default=None, ge=0)
    notes: str = ""

    @field_validator("value")
    @classmethod
    def _value_required_for_selector(cls, value: str, info: Any) -> str:
        strategy_type = info.data.get("type")
        if strategy_type == "accelerator":
            return value
        if not value:
            raise ValueError(f"策略 type={strategy_type!r} 需要非空 value")
        return value


class TargetRules(BaseModel):
    """单个客户端（trae/qoder/workbuddy）的规则。"""

    model_config = ConfigDict(extra="forbid")

    display_name: str
    title_keywords: list[str] = Field(min_length=1)
    class_name: str | None = None
    input: list[Strategy] = Field(default_factory=list, min_length=1)
    send: list[Strategy] = Field(default_factory=list, min_length=1)
    output: list[Strategy] = Field(default_factory=list, min_length=1)
    completion_marker: str = COMPLETION_MARKER
    client_version: str = ""
    collected_at: str = ""


class WindowRules(BaseModel):
    """规则文件根模型。"""

    model_config = ConfigDict(extra="forbid")

    rules_version: str = ""
    clients: dict[str, TargetRules]

    @field_validator("clients")
    @classmethod
    def _known_clients_only(cls, value: dict[str, TargetRules]) -> dict[str, TargetRules]:
        unknown = sorted(set(value) - set(WIN_KEYS))
        if unknown:
            raise ValueError(f"未知客户端键：{unknown}；允许：{list(WIN_KEYS)}")
        missing = sorted(set(WIN_KEYS) - set(value))
        if missing:
            raise ValueError(f"缺少客户端规则：{missing}")
        return value

    def get(self, win_key: str) -> TargetRules:
        """按 win_key 取规则；不存在时抛结构化错误。"""
        try:
            return self.clients[win_key]
        except KeyError as exc:
            raise ToolError(
                ErrorCode.WINDOW_NOT_FOUND,
                f"规则中未配置客户端：{win_key}",
                detail={"win_key": win_key, "available": sorted(self.clients)},
            ) from exc

    @property
    def client_keys(self) -> list[str]:
        return list(self.clients)


def _strip_comments(node: Any) -> Any:
    """递归剔除以下划线开头的说明型键（``_comment`` 等），保持模型严格校验。

    JSON 不支持注释，模板里的字段说明只能写成 ``_comment`` 之类的键；
    只允许下划线前缀，其它未知字段仍然报错，避免手误打错字段名被静默忽略。
    """
    if isinstance(node, dict):
        return {
            key: _strip_comments(value)
            for key, value in node.items()
            if not (isinstance(key, str) and key.startswith("_"))
        }
    if isinstance(node, list):
        return [_strip_comments(item) for item in node]
    return node


def parse_window_rules(document: Any, *, source: str = "<memory>") -> WindowRules:
    """从已解析的 JSON 对象构造规则，失败时抛 RULES_INVALID 并带字段路径。"""
    try:
        return WindowRules.model_validate(_strip_comments(document))
    except ValidationError as exc:
        raise ToolError(
            ErrorCode.RULES_INVALID,
            f"window_rules 校验失败：{source}",
            detail={
                "source": source,
                "errors": [
                    {"loc": ".".join(str(p) for p in err["loc"]), "msg": err["msg"]}
                    for err in exc.errors()
                ],
            },
        ) from exc


def load_window_rules(path: str | Path) -> WindowRules:
    """读取并校验规则文件。"""
    rules_path = Path(path)
    if not rules_path.is_file():
        raise ToolError(
            ErrorCode.RULES_INVALID,
            f"window_rules 文件不存在：{rules_path}",
            detail={"path": str(rules_path)},
        )

    try:
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError(
            ErrorCode.RULES_INVALID,
            f"window_rules JSON 语法错误：{rules_path}",
            detail={"path": str(rules_path), "reason": str(exc)},
        ) from exc

    return parse_window_rules(raw, source=str(rules_path))
