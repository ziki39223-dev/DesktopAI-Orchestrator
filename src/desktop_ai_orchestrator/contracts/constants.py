"""全局常量与枚举：工具契约中被多处引用的固定值。

结束标记等值只能从这里取，禁止业务代码硬编码（见 docs/04-dev-rules.md §5.2）。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, get_args

#: 任务结束标记。上层编排与客户端 prompt 约定必须使用同一字符串。
COMPLETION_MARKER: Final[str] = "【Agent任务完成】"

#: 支持的客户端标识（一期单窗口串行，不支持实例后缀）。
WinKey = Literal["trae", "qoder", "workbuddy"]

#: 全部合法 win_key，顺序即 list_target_windows 默认返回顺序。
WIN_KEYS: Final[tuple[str, ...]] = get_args(WinKey)

#: fetch_output 单次调用默认等待秒数。
DEFAULT_TIMEOUT_S: Final[float] = 30.0

#: fetch_output 单次调用允许的最大等待秒数。
MAX_TIMEOUT_S: Final[float] = 300.0

#: send_prompt 允许的最大 prompt 字符数。
DEFAULT_MAX_PROMPT_CHARS: Final[int] = 20_000


class BackendKind(StrEnum):
    """后端类型，同时作为出参里 ``backend`` 字段的取值。"""

    MOCK = "mock"
    REAL = "real"


class FetchStatus(StrEnum):
    """fetch_output 的结果状态。

    ``ok=True`` 下的四种状态都是正常返回，"未完成"不是错误
    （见 docs/07-decision-log.md ADR-005）。
    """

    COMPLETED = "completed"
    GENERATING = "generating"
    TIMEOUT = "timeout"
    IDLE = "idle"
