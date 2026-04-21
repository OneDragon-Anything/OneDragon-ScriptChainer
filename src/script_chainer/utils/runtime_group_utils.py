from __future__ import annotations

from dataclasses import dataclass

from script_chainer.config.script_config import ScriptConfig


@dataclass
class RuntimeGroup:
    """预处理后的运行组。"""

    host: ScriptConfig
    scripts: list[ScriptConfig]


def build_runtime_groups(
    script_list: list[ScriptConfig],
    attach_targets: list[ScriptConfig | None],
) -> tuple[list[RuntimeGroup], list[str]]:
    """预处理运行组，并剔除不参与本次运行的脚本。

    Returns:
        groups: 按实际运行顺序分好的运行组。
        skipped_messages: 需要输出的跳过提示。
    """
    groups: list[RuntimeGroup] = []
    skipped_messages: list[str] = []

    for i, script_config in enumerate(script_list):
        attach_target = attach_targets[i]
        if not script_config.enabled:
            skipped_messages.append(f'脚本已禁用 跳过 {script_config.script_display_name}')
            continue
        if attach_target is not None and not attach_target.enabled:
            skipped_messages.append(f'被挂靠脚本已禁用 跳过 {script_config.script_display_name}')
            continue

        host = attach_target if attach_target is not None else script_config
        if groups and groups[-1].host is host:
            groups[-1].scripts.append(script_config)
        else:
            groups.append(RuntimeGroup(host=host, scripts=[script_config]))

    return groups, skipped_messages
