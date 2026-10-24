"""后端路由。

``Build`` 只在启动时发生一次（或 ``reload_window_rules`` 后重建），
工具调用期不做模式判断，避免“一半 mock 一半 real”的中间态。
"""

from __future__ import annotations

import logging

from ..backends.base import Backend
from ..config.rules import WindowRules, load_window_rules
from ..config.settings import AppSettings
from ..contracts.constants import BackendKind
from ..contracts.errors import ErrorCode, ToolError

_log = logging.getLogger("dao.routers")


def build_backend(settings: AppSettings) -> Backend:
    """按配置构造后端；real 模式缺依赖或非 Windows 时抛 ``DEPENDENCY_MISSING``。"""
    rules = load_window_rules(settings.window_rules_path)

    if settings.mode is BackendKind.MOCK:
        from ..backends.mock import MockBackend

        _log.info("后端=mock（开发机模式，不触碰任何 GUI）")
        return MockBackend(
            rules=rules,
            settings=settings.mock,
            rules_path=str(settings.window_rules_path),
        )

    from ..backends.real import RealBackend
    from ..backends.real.windows_driver import WindowsDriver

    # WindowsDriver 构造时会做平台与依赖校验，缺失即抛 DEPENDENCY_MISSING。
    driver = WindowsDriver()
    _log.info("后端=real（UIA + 窗口捕获）")
    return RealBackend(
        rules=rules,
        driver=driver,
        settings=settings.real,
        rules_path=str(settings.window_rules_path),
    )


class BackendRouter:
    """持有当前后端实例，并在规则重载后做必要的重建。

    ``backend`` 参数仅供测试注入 Fake 驱动；生产路径一律按 ``settings.mode`` 构造。
    """

    def __init__(self, settings: AppSettings, *, backend: Backend | None = None) -> None:
        self._settings = settings
        self._rules: WindowRules = load_window_rules(settings.window_rules_path)
        self._backend: Backend = backend if backend is not None else build_backend(settings)

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def rules(self) -> WindowRules:
        return self._rules

    def reload_rules(self, path: str | None = None) -> WindowRules:
        """重载规则并把新规则交给当前后端（不重建后端实例，保留会话状态）。"""
        target = path or str(self._settings.window_rules_path)
        rules = self._backend.reload_window_rules(path=target)
        if not rules.loaded:  # 防御：理论不可达
            raise ToolError(ErrorCode.RULES_INVALID, "规则重载未生效", detail={"path": target})

        self._rules = load_window_rules(target)
        _log.info("窗口规则已重载：%s（version=%s）", target, self._rules.rules_version)
        return self._rules

    def close(self) -> None:
        """释放后端资源（当前后端无长连接，预留扩展）。"""
        return None
