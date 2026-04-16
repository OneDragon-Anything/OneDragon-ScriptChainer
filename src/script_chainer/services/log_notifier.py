from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from one_dragon.base.operation.notify_pool import NotifyPool
from one_dragon.utils.log_utils import log

if TYPE_CHECKING:
    from script_chainer.context.script_chainer_context import ScriptChainerContext


class LogNotifier:
    """定时将收集的 stdout 日志行通过通知池合并推送。"""

    def __init__(
        self,
        ctx: ScriptChainerContext,
        title: str,
        interval: int,
    ) -> None:
        self._ctx = ctx
        self._title = title
        self._interval = interval
        self._pool = NotifyPool()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._stopped = False

    def add(self, content: str) -> None:
        """线程安全地向通知池添加一行日志。"""
        with self._lock:
            self._pool.add(content)

    def start(self) -> None:
        """启动定时推送。"""
        self._stopped = False
        self._schedule_next()

    def stop(self) -> None:
        """停止定时推送，推送剩余日志并清空通知池。"""
        self._stopped = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._flush()

    def _schedule_next(self) -> None:
        if self._stopped:
            return
        self._timer = threading.Timer(self._interval, self._on_tick)
        self._timer.daemon = True
        self._timer.start()

    def _on_tick(self) -> None:
        if self._stopped:
            return
        self._flush()
        self._schedule_next()

    def _flush(self) -> None:
        with self._lock:
            if len(self._pool) == 0:
                return
            items = list(self._pool.items)
            self._pool.clear()
        try:
            self._ctx.push_service.push_merged_async(
                title=self._title,
                items=items,
            )
        except Exception:
            log.error('定时推送日志失败', exc_info=True)
