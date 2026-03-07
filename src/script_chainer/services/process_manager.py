"""
进程管理器模块

参考 AUTO-MAS 项目的 ProcessManager:
- 封装进程生命周期管理
- 支持优雅终止 (terminate → wait → kill)
- 支持 ProcessInfo 灵活匹配 (pid/name/exe/cmdline)
- 支持目标进程追踪 (launcher 启动的子进程)
- 使用 CREATION_FLAGS 隐藏 Windows 控制台窗口

本模块的设计参考了 AUTO-MAS 项目 (https://github.com/AUTO-MAS-Project/AUTO-MAS)
的进程管理实现，特此致谢。

AUTO-MAS 原始代码版权声明:
  AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
  Copyright © 2024-2025 DLmaster361
  Copyright © 2025 MoeSnowyFox
  Copyright © 2025-2026 AUTO-MAS Team

  AUTO-MAS is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published
  by the Free Software Foundation, either version 3 of the License,
  or (at your option) any later version.

  AUTO-MAS is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty
  of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
  the GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

  Contact: DLmaster_361@163.com
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import psutil

# Windows 下隐藏控制台窗口的标志
CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


@dataclass
class ProcessInfo:
    """用于标识目标进程的数据类。

    任何非 None 字段都会用于匹配。

    Attributes:
        pid: 进程 ID。
        name: 进程名称。
        exe: 可执行文件路径。
        cmdline: 命令行参数列表。
    """

    pid: int | None = None
    name: str | None = None
    exe: str | None = None
    cmdline: list[str] | None = None


@dataclass
class ProcessResult:
    """子进程执行结果。

    Attributes:
        stdout: 标准输出内容。
        stderr: 标准错误内容。
        returncode: 返回码。
    """

    stdout: str
    stderr: str
    returncode: int


def match_process(proc: psutil.Process, target: ProcessInfo) -> bool:
    """检查进程是否与目标进程信息匹配。

    所有非 None 字段都必须匹配才返回 True。

    Args:
        proc: 待检查的 psutil 进程对象。
        target: 目标进程匹配条件。

    Returns:
        是否匹配。
    """
    try:
        if target.pid is not None and proc.pid != target.pid:
            return False
        if target.name is not None and proc.name() != target.name:
            return False
        if target.exe is not None:
            try:
                if Path(proc.exe()) != Path(target.exe):
                    return False
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                return False
        if target.cmdline is not None and proc.cmdline() != target.cmdline:
            return False
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    return True


def find_process_by_info(target: ProcessInfo) -> psutil.Process | None:
    """根据 ProcessInfo 查找第一个匹配的进程。

    Args:
        target: 目标进程匹配条件。

    Returns:
        匹配的进程对象，未找到返回 None。
    """
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if match_process(proc, target):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None


def is_process_existed(process_name: str | None) -> bool:
    """判断指定名称的进程是否存在。

    Args:
        process_name: 进程名称。

    Returns:
        进程是否存在。
    """
    if not process_name:
        return False
    return find_process_by_info(ProcessInfo(name=process_name)) is not None


class ProcessManager:
    """进程管理器，封装子进程的启动、跟踪和终止。

    支持两种模式:
        - 直接模式: 直接跟踪通过 open_process 启动的子进程。
        - 目标模式: 跟踪由启动的子进程再派生出的目标进程。

    Attributes:
        process: 直接启动的子进程。
        target_process: 追踪的目标进程。
    """

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.target_process: psutil.Process | None = None

    @property
    def main_pid(self) -> int | None:
        """获取被管理的主进程 PID。"""
        if self.target_process is not None:
            return self.target_process.pid
        if self.process is not None:
            return self.process.pid
        return None

    @property
    def main_name(self) -> str | None:
        """获取被管理的主进程名称。"""
        if self.target_process is not None:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                return self.target_process.name()
        if self.process is not None:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                return psutil.Process(self.process.pid).name()
        return None

    def open_process(
        self,
        program: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        target_process: ProcessInfo | None = None,
        search_timeout: float = 60,
    ) -> bool:
        """启动子进程。

        Args:
            program: 可执行文件路径。
            args: 启动参数列表。
            cwd: 工作目录，默认为 program 所在目录。
            target_process: 目标进程信息（用于追踪 launcher 启动的子进程）。
            search_timeout: 搜索目标进程的超时时间（秒）。

        Returns:
            是否成功启动并追踪到进程。
        """
        if self.is_running():
            self.kill()
        else:
            self.clear()

        command = [program]
        if args:
            command.extend(args)

        if cwd is None:
            cwd = os.path.dirname(program)

        try:
            self.process = subprocess.Popen(
                command,
                cwd=cwd,
                creationflags=CREATION_FLAGS,
            )
        except Exception:
            return False

        # 若指定了目标进程，则搜索并追踪
        if target_process is not None:
            return self.search_process(target_process, search_timeout)

        return True

    def search_process(
        self,
        target: ProcessInfo,
        timeout: float = 60,
        poll_interval: float = 0.5,
    ) -> bool:
        """搜索并追踪目标进程。

        优先从已启动子进程的进程树中搜索，找不到时再进行全局搜索。

        Args:
            target: 目标进程信息。
            timeout: 超时时间（秒）。
            poll_interval: 轮询间隔（秒）。

        Returns:
            是否找到目标进程。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            # 优先从已启动进程的子进程树中搜索
            found = self._search_in_children(target)
            if found is None:
                # fallback: 全局搜索
                found = find_process_by_info(target)
            if found is not None:
                self.target_process = found
                return True
            time.sleep(poll_interval)
        return False

    def _search_in_children(self, target: ProcessInfo) -> psutil.Process | None:
        """从已启动子进程的后代中搜索匹配的目标进程。

        Args:
            target: 目标进程匹配条件。

        Returns:
            匹配的进程对象，未找到返回 None。
        """
        if self.process is None:
            return None
        try:
            parent = psutil.Process(self.process.pid)
            for child in parent.children(recursive=True):
                with suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    if match_process(child, target):
                        return child
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None

    def is_running(self) -> bool:
        """检查被管理的进程是否仍在运行。"""
        if self.target_process is not None:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                return self.target_process.is_running()
            return False
        if self.process is not None:
            return self.process.poll() is None
        return False

    def kill(self, graceful_timeout: float = 3) -> None:
        """终止被管理的进程及其子进程树。

        先尝试优雅终止 (terminate)，超时后强制杀死 (kill)。

        Args:
            graceful_timeout: 优雅终止等待时间（秒）。
        """
        # 先终止子进程树
        self._kill_children(graceful_timeout)

        # 终止目标进程（psutil.Process）
        if self.target_process is not None:
            _graceful_kill_psutil(self.target_process, graceful_timeout)

        # 终止直接子进程（subprocess.Popen）
        if self.process is not None and self.process.poll() is None:
            _graceful_kill_popen(self.process, graceful_timeout)

        self.clear()

    def _kill_children(self, graceful_timeout: float = 3) -> None:
        """终止被管理进程的所有子进程（进程树清理）。

        通过 PID 精确定位子进程，不会误杀无关进程。

        Args:
            graceful_timeout: 优雅终止等待时间（秒）。
        """
        main_proc = None
        if self.target_process is not None:
            main_proc = self.target_process
        elif self.process is not None:
            with suppress(psutil.NoSuchProcess):
                main_proc = psutil.Process(self.process.pid)

        if main_proc is None:
            return

        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            children = main_proc.children(recursive=True)
            for child in children:
                _graceful_kill_psutil(child, graceful_timeout)

    def clear(self) -> None:
        """清空跟踪的进程信息。"""
        self.process = None
        self.target_process = None

    @staticmethod
    def run_process(
        command: list[str],
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> ProcessResult:
        """一次性执行命令并捕获输出。

        适用于执行简短命令并获取结果。

        Args:
            command: 命令及参数列表。
            cwd: 工作目录。
            timeout: 超时时间（秒）。

        Returns:
            ProcessResult 包含 stdout、stderr 和 returncode。
        """
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=CREATION_FLAGS,
            )
            return ProcessResult(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ProcessResult(stdout='', stderr='执行超时', returncode=-1)
        except Exception as e:
            return ProcessResult(stdout='', stderr=str(e), returncode=-1)


def _graceful_kill_psutil(proc: psutil.Process, graceful_timeout: float = 3) -> None:
    """优雅终止一个 psutil.Process: terminate -> wait -> kill。

    Args:
        proc: 要终止的进程。
        graceful_timeout: 等待时间（秒）。
    """
    with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        if not proc.is_running():
            return
        try:
            proc.terminate()
            proc.wait(timeout=graceful_timeout)
        except psutil.TimeoutExpired:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                proc.kill()
                with suppress(psutil.TimeoutExpired):
                    proc.wait(timeout=graceful_timeout)


def _graceful_kill_popen(proc: subprocess.Popen, graceful_timeout: float = 3) -> None:
    """优雅终止一个 subprocess.Popen: terminate -> wait -> kill。

    Args:
        proc: 要终止的进程。
        graceful_timeout: 等待时间（秒）。
    """
    with suppress(ProcessLookupError, OSError):
        try:
            proc.terminate()
            proc.wait(timeout=graceful_timeout)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError, OSError):
                proc.kill()
                with suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=graceful_timeout)

