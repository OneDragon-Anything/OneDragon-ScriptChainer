from __future__ import annotations

import os
import sys
from pathlib import Path

import script_chainer


def build_runner_command(chain_name: str, script_index: int | None = None) -> tuple[list[str], str | None]:
    """构造 runner 启动命令。"""
    if getattr(sys, 'frozen', False):
        command = [
            sys.executable,
            '--onedragon',
            '--chain',
            chain_name,
        ]
        if script_index is not None:
            command.extend(['--debug-index', str(script_index)])
        return command, os.path.dirname(sys.executable) or None

    command = [
        get_console_python_executable(),
        '-m',
        'script_chainer.win_exe.script_runner',
        '--chain',
        chain_name,
    ]
    if script_index is not None:
        command.extend(['--debug-index', str(script_index)])
    return command, str(get_src_root())


def get_console_python_executable() -> str:
    """获取当前工作目录 `.venv` 内的 Python 解释器。"""
    current_dir = Path.cwd().resolve()
    candidates = [
        current_dir / '.venv' / 'Scripts' / 'python.exe',
        current_dir / '.venv' / 'bin' / 'python',
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(f'未找到当前目录虚拟环境解释器: {current_dir / ".venv"}')


def get_src_root() -> Path:
    """获取 `src/` 目录路径。"""
    package_dir = Path(script_chainer.__file__).resolve().parent
    return package_dir.parent
