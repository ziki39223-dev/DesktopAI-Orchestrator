"""重试策略：同步调用的有限次重试 + 固定/指数退避。

只用于"可重试的定位类操作"（UIA 树刷新、窗口刚被激活），不用于发送/写入——
写入重试会产生重复消息。
"""

from __future__ import annotations

import time
from collections.abc import Callable


def retry_call[T](
    func: Callable[[], T],
    *,
    attempts: int = 3,
    delay_s: float = 0.2,
    backoff: float = 2.0,
    on_error: tuple[type[BaseException], ...] = (Exception,),
    should_retry: Callable[[BaseException], bool] | None = None,
) -> T:
    """尝试执行 ``func``，失败按退避重试，最终仍失败则抛出最后一次异常。

    Args:
        attempts: 总尝试次数（>=1）。
        delay_s: 首次重试前等待秒数。
        backoff: 每次重试的等待倍数。
        on_error: 需要捕获并重试的异常类型。
        should_retry: 额外判定；返回 False 时立即抛出，不再重试。
    """
    if attempts < 1:
        raise ValueError("attempts 必须 >= 1")

    wait = delay_s
    last_error: BaseException | None = None
    for index in range(attempts):
        try:
            return func()
        except on_error as exc:
            last_error = exc
            if should_retry is not None and not should_retry(exc):
                raise
            if index == attempts - 1:
                raise
            time.sleep(wait)
            wait *= backoff

    # 理论不可达：循环内要么 return 要么 raise。
    assert last_error is not None
    raise last_error
