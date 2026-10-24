"""工具服务：把后端能力包装成带信封的契约结果。

这里同时负责：
- 生成 ``correlation_id`` 与 ``elapsed_ms``；
- 统一捕获 ``ToolError`` 与未预期异常，转成结构化错误；
- 记录每个工具调用的日志（入参摘要、后端、耗时、错误码）。
"""

from __future__ import annotations

import logging
from typing import Any

from ..backends.base import Backend
from ..common.ids import new_correlation_id
from ..common.text import preview
from ..config.settings import AppSettings
from ..contracts.errors import ErrorCode, ToolError, ToolErrorInfo
from ..contracts.tools import (
    FetchOutputData,
    FetchOutputRequest,
    ListTargetWindowsData,
    ListTargetWindowsRequest,
    ReloadWindowRulesData,
    ReloadWindowRulesRequest,
    SendPromptData,
    SendPromptRequest,
    ToolEnvelope,
    failure_envelope,
    success_envelope,
)
from ..observability.timing import Stopwatch
from ..routers.backend_router import BackendRouter

_log = logging.getLogger("dao.tools")


class ToolService:
    """四个工具的调用入口，供 MCP 层注册。"""

    def __init__(self, router: BackendRouter) -> None:
        self._router = router

    @property
    def backend(self) -> Backend:
        return self._router.backend

    # ------------------------------------------------------------------ 工具

    def list_target_windows(
        self, request: ListTargetWindowsRequest | None = None
    ) -> ToolEnvelope[ListTargetWindowsData]:
        req = request or ListTargetWindowsRequest()
        return self._run(
            "list_target_windows",
            {"include_unavailable": req.include_unavailable},
            lambda: self.backend.list_target_windows(include_unavailable=req.include_unavailable),
        )

    def send_prompt(self, request: SendPromptRequest) -> ToolEnvelope[SendPromptData]:
        return self._run(
            "send_prompt",
            {
                "win_key": request.win_key,
                "prompt_len": len(request.prompt),
                "prompt_preview": preview(request.prompt),
                "append_marker": request.append_marker,
            },
            lambda: self.backend.send_prompt(
                win_key=request.win_key,
                prompt=request.prompt,
                append_marker=request.append_marker,
            ).data,
        )

    def fetch_output(self, request: FetchOutputRequest) -> ToolEnvelope[FetchOutputData]:
        return self._run(
            "fetch_output",
            {
                "win_key": request.win_key,
                "timeout_s": request.timeout_s,
                "since_last_send": request.since_last_send,
            },
            lambda: self.backend.fetch_output(
                win_key=request.win_key,
                timeout_s=request.timeout_s,
                since_last_send=request.since_last_send,
                max_chars=request.max_chars,
            ),
        )

    def reload_window_rules(
        self, request: ReloadWindowRulesRequest | None = None
    ) -> ToolEnvelope[ReloadWindowRulesData]:
        req = request or ReloadWindowRulesRequest()
        return self._run(
            "reload_window_rules",
            {"path": req.path},
            lambda: self.backend.reload_window_rules(path=req.path),
        )

    # ------------------------------------------------------------------ 内部

    def invalid(self, tool_name: str, exc: Any) -> dict[str, Any]:
        """把入参校验异常（pydantic.ValidationError）转成契约错误信封的 dict。

        放在工具服务里而不是 server 层，是为了让 server 层只做「解析入参 → 调服务」。
        """
        fields = [
            {"loc": ".".join(str(part) for part in err["loc"]), "msg": err["msg"]}
            for err in getattr(exc, "errors", lambda: [])()
        ]
        correlation_id = new_correlation_id()
        _log.warning(
            "tool=%s cid=%s → INVALID_ARGUMENT %s",
            tool_name,
            correlation_id,
            [field["loc"] for field in fields],
        )
        return failure_envelope(
            ToolErrorInfo(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"{tool_name} 入参校验失败",
                detail={"fields": fields},
            ),
            backend=self.backend.kind,
            correlation_id=correlation_id,
            elapsed_ms=0,
        ).model_dump(mode="json")

    def _run(
        self,
        tool_name: str,
        args_summary: dict[str, Any],
        action: Any,
    ) -> ToolEnvelope[Any]:
        """统一执行 + 计时 + 错误映射 + 日志。"""
        correlation_id = new_correlation_id()
        backend_kind = self.backend.kind

        with Stopwatch() as watch:
            try:
                data = action()
            except ToolError as exc:
                elapsed = watch.elapsed_ms
                _log.warning(
                    "tool=%s cid=%s backend=%s args=%s → %s (%dms) %s",
                    tool_name,
                    correlation_id,
                    backend_kind.value,
                    args_summary,
                    exc.code.value,
                    elapsed,
                    exc.message,
                )
                return failure_envelope(
                    exc.to_info(),
                    backend=backend_kind,
                    correlation_id=correlation_id,
                    elapsed_ms=elapsed,
                )
            except Exception as exc:  # 兜底：不允许裸异常冒到 MCP 层
                elapsed = watch.elapsed_ms
                _log.exception(
                    "tool=%s cid=%s backend=%s args=%s → INTERNAL_ERROR (%dms)",
                    tool_name,
                    correlation_id,
                    backend_kind.value,
                    args_summary,
                    elapsed,
                )
                return failure_envelope(
                    ToolErrorInfo(
                        code=ErrorCode.INTERNAL_ERROR,
                        message=f"未预期错误：{type(exc).__name__}",
                        detail={"reason": str(exc)},
                    ),
                    backend=backend_kind,
                    correlation_id=correlation_id,
                    elapsed_ms=elapsed,
                )

        elapsed = watch.elapsed_ms
        _log.info(
            "tool=%s cid=%s backend=%s args=%s → OK (%dms)",
            tool_name,
            correlation_id,
            backend_kind.value,
            args_summary,
            elapsed,
        )
        return success_envelope(
            data,
            backend=backend_kind,
            correlation_id=correlation_id,
            elapsed_ms=elapsed,
        )


def build_service(settings: AppSettings) -> ToolService:
    """按配置构建工具服务（启动时调用一次）。"""
    return ToolService(BackendRouter(settings))
