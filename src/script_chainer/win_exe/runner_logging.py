from __future__ import annotations

import logging
import sys
from pathlib import Path

from one_dragon.utils.log_utils import (
    ProjectRuntimeLoggingContext,
    configure_project_runtime_logging,
    get_log_file_path,
)

RUNNER_LOGGER_NAME = 'ScriptChainerRunner'
RUNNER_LOG_FILE_NAME = 'script_chainer_runner.log'
RUNNER_FRAMEWORK_LOG_FILE_NAME = 'script_chainer_framework.log'
log = logging.getLogger(RUNNER_LOGGER_NAME)


def _get_runner_log_dir() -> Path | None:
    """获取 runner 日志目录。"""
    if getattr(sys, 'frozen', False):
        log_dir = Path(sys.executable).resolve().parent / '.log'
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    return None


def get_runner_log_file_path(file_name: str = RUNNER_LOG_FILE_NAME) -> str:
    """获取 runner 相关日志文件路径。

    打包运行时，日志固定写入程序所在目录下的 `.log/`；
    源码模式下沿用框架默认的工作目录日志路径。
    """
    log_dir = _get_runner_log_dir()
    if log_dir is not None:
        return str(log_dir / file_name)
    return get_log_file_path(default_name=file_name)


def configure_runner_runtime_logging() -> ProjectRuntimeLoggingContext:
    """显式启用 runner 进程的项目日志与框架日志分流。"""
    runner_log_file = get_runner_log_file_path(RUNNER_LOG_FILE_NAME)
    framework_log_file = get_runner_log_file_path(RUNNER_FRAMEWORK_LOG_FILE_NAME)
    context = configure_project_runtime_logging(
        project_logger_name=RUNNER_LOGGER_NAME,
        project_log_file_path=runner_log_file,
        framework_log_file_path=framework_log_file,
        project_add_console_handler=False,
        framework_add_console_handler=False,
    )
    log.info('runner log file: %s', context.project_log_file_path)
    log.info('framework log file: %s', context.framework_log_file_path)
    return context
