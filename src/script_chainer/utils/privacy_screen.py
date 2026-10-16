"""运行脚本链期间的隐私屏。

在物理屏幕上盖一块 TOPMOST 全屏黑窗，并用
``SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`` 让这块窗口对截图 / 录屏 /
远程桌面不可见：人眼看到的是黑屏，捕获 API 拍到的是窗口下方的真实画面，因此
脚本自身的画面识别不受影响。

实现是纯 Win32（ctypes），不依赖 Qt、不新增进程，可以直接跑在没有 Qt 事件循环的
runner 进程里；窗口与消息循环挂在后台线程，不阻塞调用方。

任何一步失败都只记录日志、不向调用方抛异常，避免影响脚本链执行。
窗口对鼠标穿透：带 ``WS_EX_LAYERED | WS_EX_TRANSPARENT``，点击会落到下层窗口。
只返回 ``HTTRANSPARENT`` 不够，那只会把命中转给同一线程里的窗口，到不了游戏进程。
可用 ``Ctrl + Alt + Shift + 主键`` 在显示和隐藏之间切换
（主键默认 F12，可在设置界面录制，见 :class:`PrivacyScreen`）。
隐藏只收起黑屏，窗口线程和热键仍在；脚本链结束或「关闭隐私屏」才会真正关掉。
"""

from __future__ import annotations

import ctypes
import re
import threading
from ctypes import wintypes

from script_chainer.win_exe.runner_logging import log

# ---------------------------------------------------------------- 常量

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

# 不透明度 255：人眼仍是纯黑，穿透靠的是 WS_EX_TRANSPARENT 而不是透明像素
LWA_ALPHA = 0x00000002
CLICK_THROUGH_ALPHA = 255

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_HOTKEY = 0x0312
WM_NCHITTEST = 0x0084
WM_APP = 0x8000
WM_PRIVACY_SHOW = WM_APP + 1
HTTRANSPARENT = -1

WDA_EXCLUDEFROMCAPTURE = 0x00000011

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

ERROR_CLASS_ALREADY_EXISTS = 1410

TOP_MOST_TIMER_ID = 1
TOP_MOST_INTERVAL_MS = 1000
EMERGENCY_HOTKEY_ID = 0x91A7

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

WINDOW_CLASS_NAME = 'OD_SCRIPT_CHAINER_PRIVACY_SCREEN'
WINDOW_TITLE = 'OneDragon ScriptChainer Privacy Screen'

DEFAULT_CLOSE_KEY = 'f12'

START_TIMEOUT_SECONDS = 5
STOP_TIMEOUT_SECONDS = 5

# ---------------------------------------------------------------- Win32

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

LRESULT = ctypes.c_longlong

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.UINT),
        ('style', wintypes.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
        ('hIconSm', wintypes.HICON),
    ]


_user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
_user32.RegisterClassExW.restype = ctypes.c_ushort

_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
_user32.CreateWindowExW.restype = wintypes.HWND

_user32.DefWindowProcW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
_user32.DefWindowProcW.restype = LRESULT

_user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
]
_user32.GetMessageW.restype = ctypes.c_int

_user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]

_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.DispatchMessageW.restype = LRESULT

_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.PostQuitMessage.argtypes = [ctypes.c_int]

_user32.PostMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
_user32.PostMessageW.restype = wintypes.BOOL

_user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
_user32.SendMessageW.restype = LRESULT

_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UpdateWindow.argtypes = [wintypes.HWND]

_user32.SetTimer.argtypes = [
    wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p
]
_user32.SetTimer.restype = ctypes.c_size_t

_user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
_user32.SetWindowPos.restype = wintypes.BOOL

_user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

_user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD
]
_user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int

_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = wintypes.BOOL

_user32.RegisterHotKey.argtypes = [
    wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT
]
_user32.RegisterHotKey.restype = wintypes.BOOL

_user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
_user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p

_gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
_gdi32.CreateSolidBrush.restype = wintypes.HBRUSH

_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE


# ---------------------------------------------------------------- 热键解析

_KEY_TO_VK_EXTRA = {
    'space': 0x20,
    'tab': 0x09,
    'enter': 0x0D,
    'esc': 0x1B,
    'escape': 0x1B,
    'backspace': 0x08,
    'delete': 0x2E,
    'insert': 0x2D,
    'home': 0x24,
    'end': 0x23,
    'page_up': 0x21,
    'page_down': 0x22,
    'up': 0x26,
    'down': 0x28,
    'left': 0x25,
    'right': 0x27,
    'minus': 0xBD,
    '-': 0xBD,
    'equals': 0xBB,
    'comma': 0xBC,
    'period': 0xBE,
    'slash': 0xBF,
    'backslash': 0xDC,
    'semicolon': 0xBA,
    'apostrophe': 0xDE,
    'grave': 0xC0,
    'l_bracket': 0xDB,
    'r_bracket': 0xDD,
}


def key_to_vk(key: str) -> int | None:
    """把按键名解析成 Windows 虚拟键码，无法识别时返回 None。

    支持 ``a``~``z``、``0``~``9``、``f1``~``f24``、``numpad_0``~``numpad_9``、
    ``vk_N`` 数字码以及 ``_KEY_TO_VK_EXTRA`` 里的常用键名。
    """
    key_name = str(key or '').strip().lower()
    if not key_name:
        return None

    vk_match = re.fullmatch(r'vk_(\d+)', key_name)
    if vk_match:
        vk = int(vk_match.group(1))
        return vk if 0 <= vk <= 254 else None

    if len(key_name) == 1 and key_name.isalnum():
        return ord(key_name.upper())

    if key_name.startswith('numpad_'):
        suffix = key_name.replace('numpad_', '', 1)
        if suffix.isdigit():
            num = int(suffix)
            if 0 <= num <= 9:
                return 0x60 + num
        return None

    fn_match = re.fullmatch(r'f(\d{1,2})', key_name)
    if fn_match:
        fn_num = int(fn_match.group(1))
        if 1 <= fn_num <= 24:
            return 0x70 + fn_num - 1

    return _KEY_TO_VK_EXTRA.get(key_name)


# ---------------------------------------------------------------- 进程级状态

_class_lock = threading.Lock()
_class_registered = False
_wndproc_callback: WNDPROC | None = None
_background_brush: int | None = None
def _set_thread_dpi_awareness() -> int | None:
    """把当前线程设为 PER_MONITOR_AWARE_V2，返回旧 context 供恢复使用。

    与进程级 ``SetProcessDpiAwarenessContext`` 不同，
    ``SetThreadDpiAwarenessContext`` 只影响当前线程，不会污染进程内其他线程
    （例如自动化软件截图所在的线程）。

    返回值是旧的 DPI_AWARENESS_CONTEXT 句柄（非 0/NULL），
    传给 :func:`_restore_thread_dpi_awareness` 即可恢复。
    失败时返回 None。
    """
    ctypes.set_last_error(0)
    old = _user32.SetThreadDpiAwarenessContext(
        ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    )
    if old:
        return int(old)
    log.warning('SetThreadDpiAwarenessContext 失败 error=%s', ctypes.get_last_error())
    return None


def _restore_thread_dpi_awareness(old_context: int | None) -> None:
    """恢复线程原来的 DPI 感知 context。"""
    if old_context is None:
        return
    _user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(old_context))


def _register_window_class() -> bool:
    """注册隐私屏窗口类，进程内只注册一次。"""
    global _class_registered, _wndproc_callback, _background_brush

    with _class_lock:
        if _class_registered:
            return True

        # 窗口类长期存在，回调与背景刷必须一直持有引用
        _wndproc_callback = WNDPROC(_window_proc)
        _background_brush = _gdi32.CreateSolidBrush(0x00000000)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = _wndproc_callback
        wc.hInstance = _kernel32.GetModuleHandleW(None)
        wc.hbrBackground = _background_brush
        wc.lpszClassName = WINDOW_CLASS_NAME

        ctypes.set_last_error(0)
        if not _user32.RegisterClassExW(ctypes.byref(wc)):
            error = ctypes.get_last_error()
            if error != ERROR_CLASS_ALREADY_EXISTS:
                log.error('注册隐私屏窗口类失败 error=%s', error)
                return False

        _class_registered = True
        return True


def _window_proc(hwnd, msg, wparam, lparam):
    """隐私屏窗口的消息处理。

    窗口本身无状态（一块纯黑板），消息处理不依赖实例，因此用模块级函数。
    """
    try:
        if msg == WM_CLOSE:
            _user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            _user32.PostQuitMessage(0)
            return 0
        if msg == WM_TIMER and wparam == TOP_MOST_TIMER_ID:
            # 隐藏期间不能带 SWP_SHOWWINDOW，否则一秒内又会被拉起来。
            if _user32.IsWindowVisible(hwnd):
                _user32.SetWindowPos(
                    hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )
            return 0
        if msg == WM_NCHITTEST:
            # 同一线程内的兜底。跨进程穿透靠 WS_EX_LAYERED | WS_EX_TRANSPARENT。
            return HTTRANSPARENT
        if msg == WM_HOTKEY and wparam == EMERGENCY_HOTKEY_ID:
            if _user32.IsWindowVisible(hwnd):
                _conceal_privacy_window(hwnd)
            else:
                _reveal_privacy_window(hwnd)
            return 0
        if msg == WM_PRIVACY_SHOW:
            if not _user32.IsWindowVisible(hwnd):
                return int(_reveal_privacy_window(hwnd))
            return 1
    except Exception:
        log.error('隐私屏窗口消息处理异常 msg=%s', msg, exc_info=True)
        return 0

    return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _conceal_privacy_window(hwnd: int) -> None:
    """暂时隐藏隐私屏。窗口、消息循环和热键都保留，以便再次打开。"""
    _user32.ShowWindow(hwnd, SW_HIDE)
    log.info('隐私屏已隐藏')


def _reveal_privacy_window(hwnd: int) -> bool:
    """先确认排除捕获，再重新显示并置顶；失败时保持隐藏。"""
    ctypes.set_last_error(0)
    if not _user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
        log.error(
            '重新显示时 SetWindowDisplayAffinity 失败 error=%s 隐私屏保持隐藏',
            ctypes.get_last_error(),
        )
        return False

    _user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    _user32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )
    log.info('隐私屏已显示')
    return True


def _enable_click_through(hwnd: int) -> bool:
    """把已带 WS_EX_LAYERED 的窗口设成不透明黑底，同时保留鼠标穿透。

    分层窗口在调用 ``SetLayeredWindowAttributes`` 之前不会正常显示。
    Alpha 取 255，画面仍是纯黑；穿透来自扩展样式，不来自透明像素。
    """
    ctypes.set_last_error(0)
    if _user32.SetLayeredWindowAttributes(hwnd, 0, CLICK_THROUGH_ALPHA, LWA_ALPHA):
        return True
    log.error('SetLayeredWindowAttributes 失败 error=%s', ctypes.get_last_error())
    return False


def _create_privacy_window(close_key: str) -> int | None:
    """创建并显示覆盖整个虚拟桌面的隐私屏窗口，失败返回 None。

    调用前应已通过 :func:`_set_thread_dpi_awareness` 设置线程级 DPI 感知，
    这样 ``GetSystemMetrics`` 才能返回物理像素而非逻辑像素。
    """
    if not _register_window_class():
        return None

    vx = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

    hwnd = _user32.CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE,
        WINDOW_CLASS_NAME, WINDOW_TITLE,
        WS_POPUP,
        vx, vy, vw, vh,
        None, None, _kernel32.GetModuleHandleW(None), None,
    )
    if not hwnd:
        log.error('创建隐私屏窗口失败 error=%s', ctypes.get_last_error())
        return None

    if not _enable_click_through(hwnd):
        _user32.DestroyWindow(hwnd)
        return None

    ctypes.set_last_error(0)
    if not _user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
        log.error(
            'SetWindowDisplayAffinity 失败 error=%s 取消显示隐私屏',
            ctypes.get_last_error(),
        )
        _user32.DestroyWindow(hwnd)
        return None

    _user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    _user32.UpdateWindow(hwnd)
    log.info('隐私屏已覆盖虚拟桌面 (%s,%s) %sx%s', vx, vy, vw, vh)

    # 修饰键固定 Ctrl+Alt+Shift，主键来自设置；解析失败时回退默认值。
    # MOD_NOREPEAT：按住不连发，避免一次按键把隐私屏来回切换。
    main_key = str(close_key or '').strip().lower()
    main_vk = key_to_vk(main_key)
    if main_vk is None:
        log.warning('隐私屏热键主键无法识别 %r 回退默认主键 %s', close_key, DEFAULT_CLOSE_KEY)
        main_key = DEFAULT_CLOSE_KEY
        main_vk = key_to_vk(main_key)

    if not _user32.RegisterHotKey(
        hwnd,
        EMERGENCY_HOTKEY_ID,
        MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT,
        main_vk,
    ):
        log.warning(
            '隐私屏开关热键 Ctrl+Alt+Shift+%s 注册失败 可能已被占用',
            main_key.upper(),
        )

    _user32.SetTimer(hwnd, TOP_MOST_TIMER_ID, TOP_MOST_INTERVAL_MS, None)
    return hwnd


class PrivacyScreen:
    """全屏隐私屏。

    ``start()`` 与 ``stop()`` 都是幂等的，且都不会抛异常；启动失败时 ``start()``
    返回 False 并记录日志。

    快捷键只在显示和隐藏之间切换，不销毁窗口。``stop()`` 才会真正关闭。

    Args:
        close_key: 开关热键的主键（修饰键固定 Ctrl+Alt+Shift），
            键名格式同 :func:`key_to_vk`；无法识别时回退默认主键 F12。
    """

    def __init__(self, close_key: str = DEFAULT_CLOSE_KEY) -> None:
        self._close_key = close_key
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._hwnd: int | None = None
        self._ready = threading.Event()

    def start(self) -> bool:
        """在后台线程拉起隐私屏，返回是否成功盖住屏幕。

        已经在运行但被快捷键隐藏时，会重新显示。
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                hwnd = self._hwnd
                if hwnd:
                    # 同步获取窗口线程的显示结果，排除捕获失败时不能报告成功。
                    return bool(_user32.SendMessageW(hwnd, WM_PRIVACY_SHOW, 0, 0))
                return False

            self._hwnd = None
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run, name='privacy_screen', daemon=True
            )
            self._thread.start()
            self._ready.wait(START_TIMEOUT_SECONDS)
            hwnd = self._hwnd

        if hwnd is None:
            log.error('隐私屏启动失败')
            return False

        return True

    def stop(self) -> None:
        """关闭隐私屏，恢复屏幕显示。"""
        with self._lock:
            thread = self._thread
            hwnd = self._hwnd
            self._thread = None
            self._hwnd = None

        if thread is None or not thread.is_alive():
            return

        if hwnd:
            _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

        thread.join(STOP_TIMEOUT_SECONDS)
        if thread.is_alive():
            log.warning('隐私屏未在 %s 秒内关闭 窗口将由进程退出回收', STOP_TIMEOUT_SECONDS)
        else:
            log.info('隐私屏已关闭')

    def _run(self) -> None:
        """窗口线程：建窗、显示，然后跑消息循环直到窗口销毁。"""
        old_dpi = _set_thread_dpi_awareness()
        try:
            hwnd = _create_privacy_window(self._close_key)
        except Exception:
            log.error('创建隐私屏窗口异常', exc_info=True)
            hwnd = None
        finally:
            # 建窗完成后立即恢复线程 DPI 感知，将对 DPI 敏感的
            # 范围缩到最小（窗口本身的属性在建窗时已锁定）。
            _restore_thread_dpi_awareness(old_dpi)

        self._hwnd = hwnd
        self._ready.set()

        if hwnd is None:
            return

        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))
