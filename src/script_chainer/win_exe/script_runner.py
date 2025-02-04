import argparse
import ctypes
import datetime
import subprocess
import time

from colorama import init, Fore, Style

from script_chainer.config.script_config import ScriptConfig, ScriptChainConfig, CheckDoneMethods

init(autoreset=True)

def get_hwnd(window_title):
    """
    根据窗口名称获取对应的句柄
    """
    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if hwnd:
        return hwnd
    else:
        return None


def is_window_exists(window_title):
    """
    判断窗口是否存在
    """
    hwnd = get_hwnd(window_title)
    return hwnd is not None


def close_window(window_title, period: float = 0.1) -> bool:
    """
    关闭一个窗口
    """
    for i in range(60):
        hwnd = get_hwnd(window_title)
        if hwnd is None:
            return True
        # 先激活hwnd再关闭
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.PostMessageA(hwnd, 0x0010, 0, 0)

        time.sleep(period)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chain', type=int, default=1, help='脚本链编号')

    return parser.parse_args()


def print_message(message: str, level="INFO"):
    # 打印消息，带有时间戳和日志级别
    time.sleep(0.1)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    colors = {"INFO": Fore.CYAN, "ERROR": Fore.YELLOW + Style.BRIGHT, "PASS": Fore.GREEN}
    color = colors.get(level, Fore.WHITE)
    print(f"{timestamp} | {color}{level}{Style.RESET_ALL} | {message}")


def run_script(script_config: ScriptConfig) -> None:
    """
    运行脚本
    """
    script_path = script_config.script_path
    args = script_config.script_arguments

    invalid_message = script_config.invalid_message
    if invalid_message is not None:
        print_message(f'脚本配置不合法 跳过运行 {invalid_message}')
        return

    command = [script_path, args]

    start_time = time.time()

    process = subprocess.Popen(command)

    game_win_ever_existed: bool = False  # 游戏窗口是否存在
    while True:
        is_done: bool = False
        if script_config.check_done == CheckDoneMethods.GAME_CLOSED.value.value:
            game_win_current_existed: bool = is_window_exists(script_config.game_window_title)
            if game_win_ever_existed and not game_win_current_existed:
                is_done = True

            game_win_ever_existed = game_win_ever_existed or game_win_current_existed

            if not game_win_ever_existed:
                print_message(f'等待打开 {script_config.game_window_title}')
            elif game_win_current_existed:
                print_message(f'正在运行 {script_config.game_window_title}')
            else:
                print_message(f'运行结束 {script_config.game_window_title}')

        now = time.time()

        if now - start_time > script_config.run_timeout_seconds:
            is_done = True
            print_message(f'脚本运行超时 {script_config.script_display_name}')

        if is_done:
            break

        time.sleep(1)

    try:
        process.kill()
        close_window(script_config.game_window_title)
    except Exception:
        pass

    print_message(f'运行结束 {script_config.game_window_title}')
    time.sleep(2)  # 稍微等待前一个窗口关闭


def run():
    args = parse_args()
    module_name: str = '%02d' % args.chain
    chain_config: ScriptChainConfig = ScriptChainConfig(module_name)
    if not chain_config.is_file_exists():
        print_message(f'脚本链配置不存在 {module_name}')
        return

    for script_config in chain_config.script_list:
        run_script(script_config)

    print_message('已完成全部脚本 5秒后关闭')
    time.sleep(5)


if __name__ == '__main__':
    run()