import argparse
import atexit
import datetime
import os
import shlex
import signal
import sys
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePath

from colorama import Fore, Style, init

from one_dragon.utils import cmd_utils
from script_chainer.config.script_config import (
    CheckDoneMethods,
    ScriptChainConfig,
    ScriptConfig,
    ScriptType,
)
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.services.log_notifier import LogNotifier
from script_chainer.services.process_manager import (
    LauncherExitError,
    ProcessInfo,
    ProcessManager,
    find_process_by_info,
    is_process_existed,
)
from script_chainer.utils.console_close_utils import force_exit_on_console_close
from script_chainer.utils.runtime_group_utils import (
    build_runtime_selection,
    resolve_runtime_groups,
)
from script_chainer.utils.wait_utils import wait_with_cancel
from script_chainer.win_exe.runner_logging import (
    configure_runner_runtime_logging,
    log,
)

# 当前活跃的 ProcessManager，用于信号处理时清理
_active_pm: ProcessManager | None = None


class _NoLogTimeoutError(Exception):
    """脚本长时间无日志输出时抛出，触发外层重试。"""


@dataclass
class _RunMonitorState:
    """单次脚本运行监控过程中的瞬态状态。"""

    script_ever_existed: bool = False
    game_ever_existed: bool = False
    last_log_time: float | None = None


class _TeeWriter:
    """包装 stdout，将每行输出同时写入 LogNotifier。"""

    def __init__(self, original: object, notifier: LogNotifier) -> None:
        self._original = original
        self._notifier = notifier

    def write(self, s: str) -> int:
        result = self._original.write(s)
        stripped = s.strip()
        if stripped:
            self._notifier.add(stripped)
        return result

    def flush(self) -> None:
        self._original.flush()

    def __getattr__(self, name: str):
        return getattr(self._original, name)


class _RunnerExitController:
    """管理 runner 的退出状态和普通信号处理。"""

    def __init__(self) -> None:
        self._shutdown_event = threading.Event()

    def wait(self, seconds: float) -> bool:
        return wait_with_cancel(self._shutdown_event, seconds)

    def reset(self) -> None:
        self._shutdown_event.clear()

    def is_shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    def exit(self, cleanup: Callable[[], None], force: bool = False) -> None:
        self._shutdown_event.set()
        cleanup()
        if force:
            os._exit(1)
        sys.exit(1)

    def install_handlers(self, cleanup: Callable[[], None]) -> None:
        def _on_exit_signal(signum, frame):
            self.exit(cleanup)

        signal.signal(signal.SIGINT, _on_exit_signal)
        signal.signal(signal.SIGTERM, _on_exit_signal)
        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, _on_exit_signal)


_exit_controller = _RunnerExitController()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chain', type=str, default='01', help='脚本链名称')
    parser.add_argument('-s', '--shutdown', type=int, nargs='?', const=60, help='运行后关机延迟秒数，默认60秒')
    parser.add_argument('--debug-index', type=int, default=None, help='仅调试指定下标脚本，并按挂靠关系一并编排（禁用项仍会跳过）')

    return parser.parse_args()


def print_message(message: str, level="INFO"):
    # 打印消息，带有时间戳和日志级别
    _exit_controller.wait(0.1)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    colors = {"INFO": Fore.CYAN, "ERROR": Fore.YELLOW + Style.BRIGHT, "PASS": Fore.GREEN}
    color = colors.get(level, Fore.WHITE)
    print(f"{timestamp} | {color}{level}{Style.RESET_ALL} | {message}")
    log.info(message)


def _push_chain_notification(
    ctx: ScriptChainerContext | None,
    chain_name: str,
    action: str,
    script_config: ScriptConfig,
) -> None:
    """按脚本配置推送脚本链通知。"""
    if ctx is None:
        return
    ctx.push_service.push_async(
        title=ctx.notify_config.title,
        content=f'脚本链 {chain_name} {action}: {script_config.script_display_name}',
    )


def _make_stdout_callback(
    display_name: str,
    log_notifier: LogNotifier | None = None,
    state: _RunMonitorState | None = None,
) -> Callable[[str], None]:
    """创建 stdout 回调，为每行输出添加前缀。

    Args:
        display_name: 显示名称。
        log_notifier: 可选的日志通知器，用于定时推送日志。
        state: 可选的运行监控状态，用于记录最后一次收到日志的时间戳。
    """
    prefix = f'{Style.DIM}[{display_name}]{Style.RESET_ALL}'

    def _on_stdout(line: str) -> None:
        print(f'{prefix} {line}', flush=True)
        log.info('[脚本] %s', line)
        if log_notifier is not None:
            log_notifier.add(line)
        if state is not None:
            state.last_log_time = time.time()

    return _on_stdout


def _launch_script(
    script_config: ScriptConfig,
    log_notifier: LogNotifier | None = None,
    state: _RunMonitorState | None = None,
) -> ProcessManager:
    """启动脚本子进程并返回 ProcessManager。

    使用 ProcessManager 封装子进程的启动，支持:
        - CREATION_FLAGS 隐藏控制台窗口。
        - 目标进程追踪（当 script_process_name 与启动器不同时）。
        - stdout 捕获并转发到控制台/日志。

    Args:
        script_config: 脚本配置。
        log_notifier: 可选的日志通知器，用于定时推送日志。
        state: 可选的运行监控状态，用于记录最后一次收到日志的时间戳。

    Returns:
        已初始化的 ProcessManager。
    """
    script_path = script_config.script_path

    # 解析启动参数
    args_list = None
    if script_config.script_arguments and script_config.script_arguments.strip():
        args_list = shlex.split(script_config.script_arguments, posix=False)

    # 如果配置了脚本进程名称，则追踪目标进程（launcher 场景）
    target = None
    if script_config.script_process_name:
        target = ProcessInfo(name=script_config.script_process_name)

    pm = ProcessManager()
    try:
        display_name = script_config.game_display_name or script_config.script_display_name or PurePath(script_path).name
        success = pm.open_process(
            program=script_path,
            args=args_list,
            target_process=target,
            search_timeout=30,
            stdout_callback=_make_stdout_callback(display_name, log_notifier, state),
        )
    except LauncherExitError as e:
        log.error('启动器异常退出: %s', e, exc_info=True)
        print_message(f'启动器异常退出 {script_path} (rc={e.returncode})', level='ERROR')
        return pm
    except Exception:
        log.error('启动子进程失败: %s', script_path, exc_info=True)
        print_message(f'脚本进程启动失败 {script_path}', level='ERROR')
        return pm

    if success:
        print_message(f'脚本进程启动成功 {script_path}', level='PASS')
    else:
        print_message(f'脚本进程启动失败 {script_path}', level='ERROR')

    return pm


def _wait_for_subprocess_ready(
    pm: ProcessManager,
    script_path: str,
    state: _RunMonitorState,
    timeout: float = 20,
    expect_target: bool = False,
) -> bool:
    """等待子进程就绪，确保进程已经成功启动并运行了一段时间。

    Args:
        pm: ProcessManager 实例。
        script_path: 脚本路径（用于日志）。
        timeout: 等待超时时间（秒）。
        expect_target: 是否期望追踪到目标进程（launcher 场景）。

    Returns:
        子进程是否就绪。
    """
    start_time = time.time()

    while True:
        now = time.time()

        if pm.process is None and pm.target_process is None:
            # 进程完全不存在
            if now - start_time > timeout:
                break
            if _exit_controller.wait(1):
                break
            continue

        if pm.is_running():
            state.script_ever_existed = True
            print_message(f'创建脚本子进程 {script_path}')
            return True
        else:
            # 进程已退出
            if pm.process is not None:
                rc = pm.process.poll()
                if rc == 0:
                    if expect_target and pm.target_process is None:
                        # launcher 退出但目标进程未就绪，继续等待
                        print_message(f'启动器已退出 (rc=0)，等待目标进程 {script_path}')
                    else:
                        print_message(f'启动器已退出 (rc=0) {script_path}')
                        return True
                else:
                    print_message(f'子进程异常退出 (rc={rc}) {script_path}', level='ERROR')

        if now - start_time > timeout:
            break

        if _exit_controller.wait(1):
            break

    return False


def _monitor_script_done(
    script_config: ScriptConfig,
    state: _RunMonitorState,
) -> None:
    """监控脚本运行状态，等待完成条件满足。

    Args:
        script_config: 脚本配置。
        state: 运行监控状态（跨 _wait_for_subprocess_ready 持久化的进程存在标志）。
    """
    start_time = time.time()
    last_status: str = ''

    no_log_timeout = script_config.no_log_timeout_seconds

    while True:
        is_done: bool = False
        status: str = ''

        # 检查游戏进程状态
        game_current_existed = is_process_existed(script_config.game_process_name)
        game_closed = state.game_ever_existed and not game_current_existed
        state.game_ever_existed = state.game_ever_existed or game_current_existed

        if script_config.game_display_name:
            if not state.game_ever_existed:
                status = f'等待打开 {script_config.game_display_name}'
            elif game_current_existed:
                status = f'正在运行 {script_config.game_display_name}'
            else:
                status = f'运行结束 {script_config.game_display_name}'
        else:
            status = f'等待 {script_config.check_done_display_name}'

        # 仅在状态变化时打印
        if status != last_status:
            print_message(status, level='PASS' if state.game_ever_existed else 'INFO')
            last_status = status

        # 检查脚本进程状态
        script_current_existed = is_process_existed(script_config.script_process_name)
        script_closed = state.script_ever_existed and not script_current_existed
        state.script_ever_existed = state.script_ever_existed or script_current_existed

        # 判断完成条件
        if script_config.check_done == CheckDoneMethods.GAME_OR_SCRIPT_CLOSED.value.value:
            if game_closed or script_closed:
                is_done = True
                print_message(f'游戏或脚本被关闭 {script_config.game_display_name}', level='PASS')
        elif script_config.check_done == CheckDoneMethods.GAME_CLOSED.value.value:
            if game_closed:
                is_done = True
                print_message(f'游戏被关闭 {script_config.game_display_name}', level='PASS')
        elif script_config.check_done == CheckDoneMethods.SCRIPT_CLOSED.value.value:
            if script_closed:
                is_done = True
                print_message(f'脚本被关闭 {script_config.script_display_name}', level='PASS')
        else:
            print_message(f'未知的检查结束方式 {script_config.check_done}', level='ERROR')
            is_done = True

        now = time.time()

        # 总运行超时检查
        if now - start_time > script_config.run_timeout_seconds:
            is_done = True
            print_message(f'脚本运行超时 {script_config.script_display_name}', level='ERROR')

        if is_done:
            break

        # 静默超时检查（无日志输出超时，触发重启）
        if (
            no_log_timeout > 0
            and state.last_log_time is not None
            and now - state.last_log_time > no_log_timeout
        ):
            print_message(
                f'脚本超过 {no_log_timeout} 秒无日志输出，判定为未响应 {script_config.script_display_name}',
                level='ERROR',
            )
            raise _NoLogTimeoutError()

        if _exit_controller.wait(1):
            break


def _cleanup_processes(script_config: ScriptConfig, pm: ProcessManager, force_script: bool = False) -> None:
    """清理脚本和游戏进程。

    通过 ProcessManager.kill() 精确终止已追踪的进程及其子进程树（基于 PID）。

    Args:
        script_config: 脚本配置。
        pm: ProcessManager 实例。
        force_script: 是否忽略用户配置，强制终止当前被管理的脚本进程。
    """
    if force_script or script_config.kill_script_after_done:
        print_message(f'尝试关闭脚本进程 {pm.main_name} (pid={pm.main_pid})')
        try:
            pm.kill()
        except Exception:
            log.error('通过 ProcessManager 关闭脚本进程失败', exc_info=True)

    if script_config.kill_game_after_done:
        game_name = script_config.game_process_name
        if game_name:
            print_message(f'尝试关闭游戏进程 {game_name}')
            try:
                proc = find_process_by_info(ProcessInfo(name=game_name))
                if proc is not None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        with suppress(Exception):
                            proc.kill()
            except Exception:
                log.error('关闭游戏进程失败', exc_info=True)


def _run_script_once(
    script_config: ScriptConfig,
    log_notifier: LogNotifier | None = None,
) -> None:
    """运行单个脚本的一次完整生命周期。

    流程:
        1. 校验配置。
        2. 启动子进程（使用 ProcessManager）。
        3. 等待子进程就绪。
        4. 监控运行状态。
        5. 清理进程。

    静默超时逻辑:
        当 script_config.no_log_timeout_seconds > 0 时，若脚本在指定时间内没有任何
        日志输出，则认为游戏/脚本未响应，会终止当前进程并向调用方抛出
        _NoLogTimeoutError，由链编排层决定是否重试和发送通知。

    Args:
        script_config: 脚本配置。
        log_notifier: 可选的日志通知器，用于定时推送日志。
    """
    global _active_pm

    invalid_message = script_config.invalid_message
    if invalid_message is not None:
        print_message(f'脚本配置不合法 跳过运行 {invalid_message}')
        return

    script_path = script_config.script_path
    no_log_timeout = script_config.no_log_timeout_seconds

    # 1. 启动脚本子进程
    state = _RunMonitorState()
    pm = _launch_script(script_config, log_notifier, state)
    _active_pm = pm
    try:
        # 2. 等待子进程就绪
        # 仅当脚本进程名与启动文件名不同时才期望追踪目标进程（launcher 场景）
        expect_target = (
            bool(script_config.script_process_name)
            and script_config.script_process_name.lower() != PurePath(script_path).name.lower()
        )
        if not _wait_for_subprocess_ready(pm, script_path, state, expect_target=expect_target):
            print_message(f'子进程创建失败 {script_path}', level='ERROR')
            pm.kill()
            return

        print_message(f'脚本子进程创建成功 {script_path}', level='PASS')
        if no_log_timeout > 0:
            state.last_log_time = time.time()

        # 3. 监控脚本运行状态
        try:
            _monitor_script_done(script_config, state)
        except _NoLogTimeoutError:
            _cleanup_processes(script_config, pm, force_script=True)
            raise

        # 4. 清理进程（正常退出路径）
        _cleanup_processes(script_config, pm)
    finally:
        _active_pm = None


def _run_external_script_with_retries(
    script_config: ScriptConfig,
    log_notifier: LogNotifier | None = None,
    ctx: ScriptChainerContext | None = None,
    chain_name: str = '',
) -> None:
    """运行外部脚本，并在静默超时时按配置重试。"""
    max_retries = (
        script_config.no_log_max_retries
        if script_config.no_log_timeout_seconds > 0
        else 0
    )
    for retry_count in range(max_retries + 1):
        if retry_count > 0:
            if log_notifier is not None:
                log_notifier.flush()
            print_message(
                f'重试运行脚本 ({retry_count}/{max_retries}) '
                f'{script_config.script_display_name}',
                level='INFO',
            )
            if script_config.notify_start:
                _push_chain_notification(
                    ctx,
                    chain_name,
                    f'无日志超时重试 ({retry_count}/{max_retries})',
                    script_config,
                )
        try:
            _run_script_once(script_config, log_notifier)
            return
        except _NoLogTimeoutError:
            if retry_count < max_retries:
                continue
            print_message(
                f'已达最大重试次数 ({max_retries})，放弃重启 '
                f'{script_config.script_display_name}',
                level='ERROR',
            )
            return


def _run_script_in_group(
    script_config: ScriptConfig,
    log_notifier: LogNotifier | None = None,
    ctx: ScriptChainerContext | None = None,
    chain_name: str = '',
) -> None:
    """运行运行组中的单个脚本。"""
    try:
        if script_config.script_type == ScriptType.PYTHON:
            _run_python_script(script_config, log_notifier)
        else:
            _run_external_script_with_retries(script_config, log_notifier, ctx, chain_name)
    except Exception:
        log.error('脚本执行异常', exc_info=True)


def _run_python_script(
    script_config: ScriptConfig,
    log_notifier: LogNotifier | None = None,
) -> None:
    """执行 Python 类型的脚本。

    读取 .py 文件并用 exec() 在当前进程中执行。

    Args:
        script_config: 脚本配置（script_type == 'python'）。
        log_notifier: 可选的日志通知器，用于定时推送日志。
    """
    script_file = Path(script_config.script_path)
    display_name = script_config.script_display_name

    invalid_msg = script_config.invalid_message
    if invalid_msg is not None:
        print_message(f'Python 脚本配置不合法 跳过运行 {invalid_msg}')
        return

    try:
        code = script_file.read_text(encoding='utf-8')
    except Exception as e:
        print_message(f'读取 Python 脚本失败 {display_name}: {e}', level='ERROR')
        log.error('读取 Python 脚本失败', exc_info=True)
        return

    if not code or not code.strip():
        print_message(f'Python 脚本为空 跳过 {display_name}')
        return

    print_message(f'执行 Python 脚本 {display_name}...')
    old_argv = sys.argv[:]
    old_sys_path = sys.path[:]
    old_stdout = sys.stdout
    old_cwd = os.getcwd()
    script_file_abs = script_file.resolve()
    script_path = str(script_file_abs)
    script_dir = script_file_abs.parent
    try:
        sys.argv = [script_path]
        sys.path.insert(0, str(script_dir))
        os.chdir(script_dir)

        if log_notifier is not None:
            sys.stdout = _TeeWriter(old_stdout, log_notifier)

        exec_globals = {
            '__name__': '__main__',
            '__file__': script_path,
            '__package__': None,
            '__spec__': None,
            '__builtins__': __builtins__,
        }
        # 只有当前进程内 exec 用户 Python 脚本时，控制台关闭才需要额外强退兜底。
        # Ctrl+C / Ctrl+Break 仍走 install_handlers() 注册的普通 signal 软退出链。
        with force_exit_on_console_close(
            lambda: _exit_controller.exit(_cleanup_active_pm, force=True)
        ):
            exec(compile(code, script_path, 'exec'), exec_globals)
            if _exit_controller.is_shutdown_requested():
                raise SystemExit(1)
        print_message(f'Python 脚本执行完成 {display_name}', level='PASS')
    except SystemExit as e:
        if _exit_controller.is_shutdown_requested():
            raise
        if e.code in (0, None):
            print_message(f'Python 脚本执行完成 {display_name}', level='PASS')
        else:
            print_message(f'Python 脚本执行失败 {display_name}: exit={e.code}', level='ERROR')
            log.error('Python 脚本通过 SystemExit 退出: %s', e.code)
    except Exception as e:
        print_message(f'Python 脚本执行失败 {display_name}: {e}', level='ERROR')
        log.error('Python 脚本执行失败', exc_info=True)
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv
        sys.path[:] = old_sys_path
        with suppress(Exception):
            os.chdir(old_cwd)


def _cleanup_active_pm():
    """清理当前活跃的 ProcessManager 子进程。"""
    global _active_pm
    if _active_pm is not None:
        with suppress(Exception):
            _active_pm.kill()
        _active_pm = None


def run_chain(chain_name: str = '01', shutdown_delay: int = 0, debug_index: int | None = None) -> None:
    """运行指定的脚本链。

    Args:
        chain_name: 脚本链名称。
        shutdown_delay: 运行后关机延迟秒数，0 表示不关机。
        debug_index: 调试脚本下标，None 表示运行整个脚本链，非负整数表示仅调试该下标脚本，
            并按编排/挂靠关系一并纳入与其关联的脚本。
    """
    _exit_controller.reset()
    configure_runner_runtime_logging()

    # 注册普通信号处理，控制台关闭强退仅在 Python exec 窗口内临时启用
    _exit_controller.install_handlers(_cleanup_active_pm)
    atexit.register(_cleanup_active_pm)

    init(autoreset=True)
    chain_config: ScriptChainConfig = ScriptChainConfig(chain_name)

    # 创建上下文实例
    ctx = None
    try:
        ctx = ScriptChainerContext()
        ctx.init()
    except Exception as e:
        log.error(f'初始化上下文实例失败: {e}')

    try:
        if not chain_config.is_file_exists():
            print_message(f'脚本链配置不存在 {chain_name}', "ERROR")
        else:
            attach_targets = chain_config.compute_attach_targets()
            try:
                selection = build_runtime_selection(
                    chain_config.script_list,
                    attach_targets,
                    debug_index=debug_index,
                )
            except ValueError as e:
                print_message(str(e), 'ERROR')
                return

            if selection.debug_target is not None:
                print_message(f'调试运行脚本链 {chain_name}: {selection.debug_target.script_display_name}')

            runtime_groups, skipped_messages = resolve_runtime_groups(selection)

            for message in skipped_messages:
                print_message(message)

            for group_idx, group in enumerate(runtime_groups):
                log_notifier: LogNotifier | None = None
                if ctx is not None and group.host.notify_log_interval > 0:
                    log_notifier = LogNotifier(
                        ctx=ctx,
                        title=f'{ctx.notify_config.title} - {group.host.script_display_name} 日志',
                        interval=group.host.notify_log_interval,
                    )
                    log_notifier.start()

                try:
                    if group.host.notify_start:
                        _push_chain_notification(
                            ctx,
                            chain_name,
                            '调试开始' if debug_index is not None else '开始运行',
                            group.host,
                        )

                    for script_config in group.scripts:
                        _run_script_in_group(script_config, log_notifier, ctx, chain_name)

                    if group.host.notify_done:
                        _push_chain_notification(
                            ctx,
                            chain_name,
                            '调试结束' if debug_index is not None else '运行结束',
                            group.host,
                        )
                finally:
                    if log_notifier is not None:
                        log_notifier.stop()

                if group_idx < len(runtime_groups) - 1:
                    print_message('10秒后开始下一个脚本')
                    if _exit_controller.wait(10):
                        break

            print_message('已完成调试脚本' if debug_index is not None else '已完成全部脚本')

        if shutdown_delay > 0:
            cmd_utils.shutdown_sys(shutdown_delay)
            print_message('准备关机')

        print_message('5秒后关闭本窗口')
        _exit_controller.wait(5)
    finally:
        # 清理资源
        if ctx is not None:
            try:
                ctx.after_app_shutdown()
            except Exception as e:
                log.error(f'清理资源失败: {e}')


def run():
    """独立运行入口"""
    args = parse_args()
    run_chain(
        chain_name=args.chain,
        shutdown_delay=args.shutdown if args.shutdown else 0,
        debug_index=args.debug_index,
    )
    sys.exit(0)


if __name__ == '__main__':
    run()
