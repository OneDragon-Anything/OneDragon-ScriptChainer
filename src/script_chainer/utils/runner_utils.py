from __future__ import annotations

import os
import sys
from one_dragon.utils.os_utils import get_path_under_work_dir


def build_runner_command(chain_name: str, script_index: int | None = None) -> tuple[list[str], str | None]:
    """构造 runner 启动命令。

    Args:
        chain_name: 脚本链名称。
        script_index: 调试脚本下标，None 表示运行整个脚本链。

    Returns:
        启动命令及其工作目录。
    """
    common_args = ["--onedragon", "--chain", chain_name]
    if script_index is not None:
        common_args.extend(["--debug-index", str(script_index)])

    # 可执行文件模式
    if getattr(sys, 'frozen', False):
        command = [sys.executable, *common_args]
        return command, os.path.dirname(sys.executable) or None
    else: # 源码模式
        launcher_work_dir = get_path_under_work_dir("src")
        command = [
            sys.executable,
            "-m",
            "script_chainer.win_exe.launcher",
            *common_args,
        ]
        return command, launcher_work_dir
