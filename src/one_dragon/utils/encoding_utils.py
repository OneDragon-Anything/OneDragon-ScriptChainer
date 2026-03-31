from __future__ import annotations

import locale
import sys


def get_console_encoding() -> str:
    """获取系统控制台编码。

    Windows 下返回 OEM 代码页（如 cp936），其他平台返回 locale 首选编码。
    """
    if sys.platform == "win32":
        import ctypes
        oem_cp = ctypes.windll.kernel32.GetOEMCP()
        return f"cp{oem_cp}"
    return locale.getpreferredencoding(False)


def decode_bytes(data: bytes, console_encoding: str) -> str:
    """自动检测编码：先尝试 UTF-8，再尝试控制台编码，最后兜底。"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode(console_encoding)
    except (UnicodeDecodeError, LookupError):
        return data.decode("utf-8", errors="replace")
