from __future__ import annotations

import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import psutil


def graceful_kill_psutil(proc: psutil.Process, timeout: float = 3) -> None:
    """优雅终止一个 psutil.Process: terminate -> wait -> kill。"""
    with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        if not proc.is_running():
            return
        try:
            proc.terminate()
            proc.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                proc.kill()
                with suppress(psutil.TimeoutExpired):
                    proc.wait(timeout=timeout)


def graceful_kill_popen(proc: subprocess.Popen, timeout: float = 3) -> None:
    """优雅终止一个 subprocess.Popen: terminate -> wait -> kill。"""
    with suppress(ProcessLookupError, OSError):
        try:
            proc.terminate()
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError, OSError):
                proc.kill()
                with suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=timeout)


def launch_in_terminal(
    command: list[str],
    cwd: str | None = None,
    title: str | None = None,
    block: bool = False,
) -> subprocess.Popen:
    """在终端窗口中启动命令。

    优先使用 Windows Terminal (wt.exe)，不可用时回退到系统默认控制台。

    Args:
        command: 命令及参数列表。
        cwd: 工作目录。
        title: 终端窗口标题（仅非阻塞的 wt 分支使用）。
        block: 是否阻塞等待命令真正结束。

    Returns:
        启动的 Popen 对象。

    说明：
        - ``block=False``（默认）：用 wt 开新标签页/窗口后**立即返回**（非阻塞）。
        - ``block=True``：Windows Terminal 开完标签页即退出，无法等待真正的子进程，
          故绕过 wt、改用新建控制台窗口（``CREATE_NEW_CONSOLE``）并 ``.wait()``——
          既有可见窗口，又能正确阻塞到脚本真正结束。
    """
    if block:
        # 阻塞：不能用 wt（开完标签页即退、等不到真进程），改用新控制台窗口并等待。
        flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        proc = subprocess.Popen(command, cwd=cwd, creationflags=flags)
        proc.wait()
        return proc

    wt_path = _find_windows_terminal()
    if wt_path is not None:
        wt_cmd = [wt_path]
        if title:
            wt_cmd.extend(['--title', title])
        if cwd:
            wt_cmd.extend(['-d', cwd])
        wt_cmd.append('--')
        wt_cmd.extend(command)
        return subprocess.Popen(wt_cmd, cwd=cwd)

    # 回退：创建新控制台窗口
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    return subprocess.Popen(command, cwd=cwd, creationflags=flags)


def _find_windows_terminal() -> str | None:
    """查找 Windows Terminal 可执行文件。"""
    if sys.platform != 'win32':
        return None

    candidates = [
        shutil.which('wt'),
        shutil.which('wt.exe'),
    ]

    local_appdata = Path.home() / 'AppData' / 'Local' / 'Microsoft' / 'WindowsApps' / 'wt.exe'
    candidates.append(str(local_appdata))

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    return None
