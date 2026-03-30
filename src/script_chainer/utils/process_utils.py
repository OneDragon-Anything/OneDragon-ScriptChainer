from __future__ import annotations

import subprocess
from contextlib import suppress

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
