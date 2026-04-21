from __future__ import annotations

import threading
import time


def sleep_interruptibly(stop_event: threading.Event, seconds: float, step: float = 0.1) -> bool:
    """可被事件打断的等待。

    Args:
        stop_event: 停止事件。
        seconds: 等待时长（秒）。
        step: 轮询粒度（秒）。

    Returns:
        是否在等待期间收到了停止信号。
    """
    if seconds <= 0:
        return stop_event.is_set()

    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return stop_event.is_set()
        if stop_event.wait(min(step, remaining)):
            return True
