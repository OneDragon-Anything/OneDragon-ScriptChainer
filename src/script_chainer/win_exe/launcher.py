import argparse
import ctypes
import sys

from one_dragon.launcher.exe_launcher import ExeLauncher
from one_dragon.version import __version__


class ScriptChainerLauncher(ExeLauncher):
    """
    千机链统一启动器
    合并 GUI 编辑器和脚本运行器为一个入口:
    - 无参数: 启动 GUI 配置编辑器
    - --onedragon: 运行脚本链
    - --chain: 指定脚本链名称（仅 --onedragon 模式）
    """

    def __init__(self):
        ExeLauncher.__init__(
            self,
            description="一条龙 千机链",
            version=__version__,
        )

    def add_custom_arguments(self, parser: argparse.ArgumentParser) -> None:
        """添加自定义参数"""
        ExeLauncher.add_custom_arguments(self, parser)
        parser.add_argument(
            "--chain",
            type=str,
            default="01",
            help="脚本链名称（仅 --onedragon 模式使用，默认: 01）",
        )
        parser.add_argument(
            "--debug-index",
            type=int,
            default=None,
            help="仅调试运行指定下标的脚本（会附带其前置/后置脚本）",
        )

    @staticmethod
    def _hide_console() -> None:
        """隐藏控制台窗口，用于 GUI 模式"""
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

    def run_gui_mode(self) -> None:
        """启动 GUI 配置编辑器"""
        self._hide_console()

        from script_chainer.win_exe.config_editor import run_editor
        run_editor()

    def run_onedragon_mode(self, launch_args) -> None:
        """运行脚本链"""
        from script_chainer.win_exe.script_runner import run_chain

        # 从 launch_args 和 self.args 中提取参数
        chain_name = self.args.chain if self.args else "01"
        shutdown_delay = self.args.shutdown if self.args and self.args.shutdown else 0
        debug_index = self.args.debug_index if self.args else None

        run_chain(
            chain_name=chain_name,
            shutdown_delay=shutdown_delay,
            debug_index=debug_index,
        )
        sys.exit(0)


def main():
    launcher = ScriptChainerLauncher()
    launcher.run()


if __name__ == "__main__":
    main()
