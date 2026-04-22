from __future__ import annotations

import logging
from dataclasses import replace

from one_dragon.utils.log_utils import (
    LoggerConfig,
    configure_logger,
    get_log_file_path,
)

RUNNER_LOGGER_NAME = 'ScriptChainerRunner'
RUNNER_LOG_FILE_NAME = 'script_chainer_runner.log'
RUNNER_LOG_CONFIG = LoggerConfig(
    default_name=RUNNER_LOG_FILE_NAME,
    add_console_handler=False,
    propagate=False,
)


def configure_runner_runtime_logging(framework_logger: logging.Logger) -> logging.Logger:
    """统一将 runner 进程内的日志切到 runner 专用文件。"""
    target_log_file = get_log_file_path(default_name=RUNNER_LOG_FILE_NAME)
    framework_logger_config = replace(
        RUNNER_LOG_CONFIG,
        log_file_path=target_log_file,
        add_console_handler=True,
        propagate=False,
    )
    configure_logger(
        framework_logger,
        framework_logger_config,
    )
    runner_logger = logging.getLogger(RUNNER_LOGGER_NAME)
    runner_logger_config = replace(
        RUNNER_LOG_CONFIG,
        log_file_path=target_log_file,
        default_name=RUNNER_LOG_FILE_NAME,
        add_console_handler=False,
        propagate=False,
    )
    configure_logger(
        runner_logger,
        runner_logger_config,
    )
    return runner_logger
