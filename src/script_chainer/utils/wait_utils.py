from __future__ import annotations

import threading
import time


def wait_with_cancel(stop_event: threading.Event, seconds: float, step: float = 0.1) -> bool:
    """可被事件打断的等待。"""
    if seconds <= 0:
        return stop_event.is_set()

    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return stop_event.is_set()
        if stop_event.wait(min(step, remaining)):
            return True
