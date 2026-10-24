"""``config.yaml`` 的模型定义。

优先级（高 → 低）：环境变量 > ``config.local.yaml`` > ``config/config.yaml`` > 内置默认。
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..contracts.constants import BackendKind


class TransportKind(StrEnum):
    """MCP 传输协议。"""

    SSE = "sse"
    STDIO = "stdio"


class ServerSettings(BaseModel):
    """SSE 服务监听参数。"""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(default="127.0.0.1", description="监听地址；局域网访问需显式改 0.0.0.0")
    port: int = Field(default=8765, ge=1, le=65535)
    sse_path: str = "/sse"
    message_path: str = "/messages/"
    #: 可选的最小防护：非空时要求请求头 ``Authorization: Bearer <token>``。
    auth_token: str = ""
    log_level: str = "INFO"


class MockSettings(BaseModel):
    """Mock 后端行为参数，用于编排侧容错联调。"""

    model_config = ConfigDict(extra="forbid")

    #: 模拟生成耗时的秒数；0 表示立刻返回已完成结果。
    latency_s: float = Field(default=0.0, ge=0.0)
    #: 未出现结束标记前，模拟"仍在生成"的轮询次数。
    generating_polls: int = Field(default=0, ge=0)
    #: 注入失败：如 ``{"trae": "SEND_FAILED"}``；空表示不注入。
    inject_errors: dict[str, str] = Field(default_factory=dict)


class RealSettings(BaseModel):
    """Real 后端行为参数。"""

    model_config = ConfigDict(extra="forbid")

    #: 定位控件时的重试次数（UIA 树刷新可能需要时间）。
    locate_attempts: int = Field(default=3, ge=1, le=10)
    locate_delay_s: float = Field(default=0.3, ge=0.0)
    #: 轮询读取输出区的间隔秒数；0 表示尽量紧凑（内部按 10ms 下限执行，避免忙等）。
    poll_interval_s: float = Field(default=1.0, ge=0.0)
    #: 发送后等待输入框清空以确认发送成功的秒数。
    send_confirm_s: float = Field(default=2.0, ge=0.0)


class AppSettings(BaseModel):
    """全局配置。"""

    model_config = ConfigDict(extra="forbid")

    mode: BackendKind = Field(default=BackendKind.MOCK, description="mock / real")
    transport: TransportKind = TransportKind.SSE
    config_dir: Path = Field(default=Path("config"))
    window_rules_path: Path = Field(default=Path("config/window_rules.json"))
    log_dir: Path | None = Field(default=Path("logs"))
    server: ServerSettings = Field(default_factory=ServerSettings)
    mock: MockSettings = Field(default_factory=MockSettings)
    real: RealSettings = Field(default_factory=RealSettings)

    @property
    def is_mock(self) -> bool:
        return self.mode is BackendKind.MOCK
