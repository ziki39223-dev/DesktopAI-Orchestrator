"""耗时统计小工具：用于出参 ``elapsed_ms``。"""

from __future__ import annotations

import time
from types import TracebackType


class Stopwatch:
    """轻量计时器，可作上下文管理器使用：``with Stopwatch() as sw: ...; sw.elapsed_ms``。"""

    __slots__ = ("_end", "_start")

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._end: float | None = None

    def stop(self) -> int:
        """结束计时并返回毫秒数（幂等）。"""
        if self._end is None:
            self._end = time.perf_counter()
        return self.elapsed_ms

    @property
    def elapsed_ms(self) -> int:
        end = self._end if self._end is not None else time.perf_counter()
        return int((end - self._start) * 1000)

    def __enter__(self) -> Stopwatch:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
