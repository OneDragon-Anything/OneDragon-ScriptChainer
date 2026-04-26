from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager


@contextmanager
def force_exit_on_console_close(force_exit: Callable[[], None]) -> Iterator[None]:
    """在上下文期间临时启用控制台关闭强退逻辑。

    这个上下文只用于当前进程内直接 ``exec()`` 用户 Python 脚本的窗口期。
    普通外部脚本路径仍然走 runner 自己的 signal 软退出链，不在这里统一强退。
    """
    handler = register_console_close_handler(force_exit)
    try:
        yield
    finally:
        unregister_console_close_handler(handler)


def register_console_close_handler(on_close: Callable[[], None]) -> object | None:
    """注册 Windows 控制台关闭事件处理器。

    仅拦截真正的控制台关闭类事件：
        - CTRL_CLOSE_EVENT (2): 点击控制台窗口右上角 X
        - CTRL_LOGOFF_EVENT (5): 用户注销
        - CTRL_SHUTDOWN_EVENT (6): 系统关机

    不拦截 Ctrl+C / Ctrl+Break，对应中断仍应走 Python signal handler，
    这样 runner 可以继续按软退出链执行 finally / atexit 等清理。

    Returns:
        注册成功时返回需要由调用方持有引用的 handler；失败或非 Windows 下返回 None。
    """
    if sys.platform != 'win32':
        return None

    import ctypes
    import ctypes.wintypes

    handler_type = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.DWORD)
    # 仅拦截真正的控制台关闭类事件，让 Ctrl+C / Ctrl+Break 继续走正常 signal 退出链。
    close_events = {2, 5, 6}

    def _handler(ctrl_type: int) -> bool:
        if ctrl_type in close_events:
            on_close()
            return True
        return False

    handler = handler_type(_handler)
    try:
        registered = bool(ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True))
    except Exception:
        return None
    return handler if registered else None


def unregister_console_close_handler(handler: object | None) -> None:
    """注销已注册的 Windows 控制台关闭事件处理器。"""
    if sys.platform != 'win32' or handler is None:
        return

    import ctypes

    try:
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, False)
    except Exception:
        return
