from __future__ import annotations

from dataclasses import dataclass

from script_chainer.config.script_config import ScriptConfig


@dataclass
class RuntimeGroup:
    """预处理后的运行组。"""

    host: ScriptConfig
    scripts: list[ScriptConfig]


@dataclass
class RuntimeSelection:
    """一次运行实际参与编排的脚本范围。"""

    script_list: list[ScriptConfig]
    attach_targets: list[ScriptConfig | None]
    debug_target: ScriptConfig | None = None

    def is_enabled(self, script: ScriptConfig) -> bool:
        """调试时仅强制启用目标脚本本身，挂靠脚本仍遵循 enabled。"""
        return script.enabled or script is self.debug_target


def build_runtime_selection(
    script_list: list[ScriptConfig],
    attach_targets: list[ScriptConfig | None],
    debug_index: int | None = None,
) -> RuntimeSelection:
    """根据调试目标裁剪本次运行真正参与的脚本。"""
    if debug_index is None:
        return RuntimeSelection(
            script_list=script_list,
            attach_targets=attach_targets,
        )

    if debug_index < 0 or debug_index >= len(script_list):
        raise ValueError(f'调试脚本下标越界: {debug_index}')

    debug_target = script_list[debug_index]
    selected_indices = {debug_index}
    for idx, attach_target in enumerate(attach_targets):
        if attach_target is debug_target:
            selected_indices.add(idx)

    return RuntimeSelection(
        script_list=[
            script_config
            for idx, script_config in enumerate(script_list)
            if idx in selected_indices
        ],
        attach_targets=[
            attach_target
            for idx, attach_target in enumerate(attach_targets)
            if idx in selected_indices
        ],
        debug_target=debug_target,
    )


def resolve_runtime_groups(
    selection: RuntimeSelection,
) -> tuple[list[RuntimeGroup], list[str]]:
    """根据本次运行选择结果，解析实际运行组并生成跳过提示。

    Returns:
        groups: 按实际运行顺序分好的运行组。
        skipped_messages: 需要输出的跳过提示。
    """
    groups: list[RuntimeGroup] = []
    skipped_messages: list[str] = []

    for i, script_config in enumerate(selection.script_list):
        attach_target = selection.attach_targets[i]
        if not selection.is_enabled(script_config):
            skipped_messages.append(f'脚本已禁用 跳过 {script_config.script_display_name}')
            continue
        if attach_target is not None and not selection.is_enabled(attach_target):
            skipped_messages.append(f'被挂靠脚本已禁用 跳过 {script_config.script_display_name}')
            continue

        host = attach_target if attach_target is not None else script_config
        if groups and groups[-1].host is host:
            groups[-1].scripts.append(script_config)
        else:
            groups.append(RuntimeGroup(host=host, scripts=[script_config]))

    return groups, skipped_messages
