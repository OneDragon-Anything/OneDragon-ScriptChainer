from __future__ import annotations

import os
import sys


def build_runner_command(chain_name: str, script_index: int | None = None) -> tuple[list[str], str | None]:
    """构造 runner 启动命令。

    Args:
        chain_name: 脚本链名称。
        script_index: 调试脚本下标，None 表示运行整个脚本链。

    Returns:
        启动命令及其工作目录。

    Raises:
        RuntimeError: 源码模式下不支持运行脚本链。
    """
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

    raise RuntimeError('源码模式下不支持运行脚本链，请使用打包后的程序。')
