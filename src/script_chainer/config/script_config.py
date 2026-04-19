import os
from dataclasses import asdict, dataclass, field, fields
from enum import Enum

from one_dragon.base.config.config_item import ConfigItem, get_config_item_from_enum
from one_dragon.base.config.yaml_config import YamlConfig


class CheckDoneMethods(Enum):

    GAME_CLOSED = ConfigItem(label='游戏被关闭', value='game_closed', desc='游戏被关闭时 认为任务完成')
    SCRIPT_CLOSED = ConfigItem(label='脚本被关闭', value='script_closed', desc='脚本被关闭时 认为任务完成')
    GAME_OR_SCRIPT_CLOSED = ConfigItem(label='游戏或脚本被关闭', value='game_or_script_closed', desc='游戏或脚本被关闭时 认为任务完成')


class ScriptProcessName(Enum):

    ONE_DRAGON_LAUNCHER = ConfigItem(label='一条龙', value='python.exe')
    ONE_DRAGON_RUNTIME_LAUNCHER = ConfigItem(label='一条龙-集成', value='OneDragon-RuntimeLauncher.exe')
    BGI = ConfigItem(label='BetterGI', value='BetterGI.exe')
    March7th = ConfigItem(label='三月七小助手', value='March7th Assistant.exe')
    MAA_BBB = ConfigItem(label='识宝小助手', value='MFAAvalonia.exe')
    SRA = ConfigItem(label='StarRailAssistant', value='SRA-cli.exe')
    MAA_END = ConfigItem(label='MaaEnd', value='MaaEnd.exe')
    MAA_GF2 = ConfigItem(label='MaaGF2Exilium', value='MaaGF2Exilium.exe')


class GameProcessName(Enum):

    GENSHIN_IMPACT_CN = ConfigItem(label='原神', value='YuanShen.exe')
    GENSHIN_IMPACT_GLOBAL = ConfigItem(label='原神（国际服）', value='GenshinImpact.exe')
    STAR_RAIL_CN = ConfigItem(label='崩坏：星穹铁道', value='StarRail.exe')
    ZZZ_CN = ConfigItem(label='绝区零', value='ZenlessZoneZero.exe')
    HONKAI_IMPACT_CN = ConfigItem(label='崩坏3', value='BH3.exe')
    ENDFIELD = ConfigItem(label='终末地', value='Endfield.exe')
    MUMU = ConfigItem(label='MUMU模拟器', value='MuMuNxDevice.exe')


class ScriptType:
    EXTERNAL = 'external'
    PYTHON = 'python'


class AttachDirection:
    NONE = ''
    UP = 'up'
    DOWN = 'down'


@dataclass
class ScriptConfig:

    script_type: str = ScriptType.EXTERNAL
    script_path: str = ''
    script_process_name: str = ''
    game_process_name: str = ''
    run_timeout_seconds: int = 3600
    check_done: str = ''
    kill_script_after_done: bool = True
    kill_game_after_done: bool = True
    script_arguments: str = ''
    notify_start: bool = True
    notify_done: bool = True
    enabled: bool = True
    attach_direction: str = AttachDirection.NONE

    # 不参与序列化的元数据
    idx: int = field(default=0, repr=False, compare=False)

    def to_dict(self) -> dict:
        """序列化为字典（排除 idx）。"""
        d = asdict(self)
        d.pop('idx', None)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> 'ScriptConfig':
        """从字典反序列化。"""
        valid = {f.name for f in fields(cls)} - {'idx'}
        return cls(**{k: v for k, v in data.items() if k in valid})

    @classmethod
    def create_default(cls) -> 'ScriptConfig':
        """创建默认配置。"""
        return cls(check_done=CheckDoneMethods.GAME_OR_SCRIPT_CLOSED.value.value)

    @classmethod
    def create_python_default(cls) -> 'ScriptConfig':
        """创建 Python 脚本类型的默认配置。"""
        return cls(
            script_type=ScriptType.PYTHON,
            notify_start=False,
            notify_done=False,
        )

    def copy(self) -> 'ScriptConfig':
        """深拷贝（保留 idx）。"""
        new = self.from_dict(self.to_dict())
        new.idx = self.idx
        return new

    @property
    def script_display_name(self) -> str:
        if self.script_path:
            return os.path.basename(self.script_path)
        return '(未设置)'

    @property
    def game_display_name(self) -> str:
        game_process_enum = [i for i in GameProcessName if i.value.value == self.game_process_name]
        return game_process_enum[0].value.label if len(game_process_enum) > 0 else self.game_process_name

    @property
    def check_done_display_name(self) -> str:
        config = get_config_item_from_enum(CheckDoneMethods, self.check_done)
        if config is not None:
            return config.label
        else:
            return ''

    @property
    def invalid_message(self) -> str | None:
        if self.script_type == ScriptType.PYTHON:
            if not self.script_path:
                return 'Python 脚本路径为空'
            elif not os.path.exists(self.script_path):
                return f'Python 脚本不存在 {self.script_path}'
            return None

        if self.script_path is None or len(self.script_path) == 0:
            return '脚本路径为空'
        elif not os.path.exists(self.script_path):
            return f'脚本路径不存在 {self.script_path}'
        elif get_config_item_from_enum(CheckDoneMethods, self.check_done) is None:
            return f'检查完成方式非法 {self.check_done}'
        elif (
                (self.check_done == CheckDoneMethods.GAME_OR_SCRIPT_CLOSED.value.value
                 or self.check_done == CheckDoneMethods.GAME_CLOSED.value.value
                 or self.kill_game_after_done)
              and (self.game_process_name is None or len(self.game_process_name) == 0)
        ):
            return '游戏进程名称为空'
        elif (
                (self.check_done == CheckDoneMethods.GAME_OR_SCRIPT_CLOSED.value.value
                 or self.check_done == CheckDoneMethods.SCRIPT_CLOSED.value.value
                 or self.kill_script_after_done)
                and (self.script_process_name is None or len(self.script_process_name) == 0)
        ):
            return '脚本进程名称为空'
        elif self.run_timeout_seconds <= 0:
            return '运行超时时间必须大于0'


class ScriptChainConfig(YamlConfig):

    def __init__(self, module_name: str, is_mock: bool = False):
        YamlConfig.__init__(
            self,
            module_name,
            sub_dir=['script_chain'],
            is_mock=is_mock, sample=False, copy_from_sample=False,
        )

        self.script_list: list[ScriptConfig] = [
            ScriptConfig.from_dict(i)
            for i in self.get('script_list', [])
        ]
        self.init_idx()

    def _get_script_chain_dir(self) -> str:
        return os.path.dirname(self.file_path)

    def _get_python_scripts_dir(self) -> str:
        d = os.path.join(self._get_script_chain_dir(), 'scripts')
        os.makedirs(d, exist_ok=True)
        return d

    def get_python_script_path(self, idx: int) -> str:
        return os.path.join(self._get_python_scripts_dir(), f'{self.module_name}_{idx}.py')

    def get_python_script_content(self, idx: int) -> str:
        path = self.script_list[idx].script_path
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ''

    def save_python_script(self, idx: int, code: str) -> str:
        path = self.script_list[idx].script_path
        if not path:
            path = self.get_python_script_path(idx)
            self.script_list[idx].script_path = path
            self.save()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        return path

    def _next_python_script_number(self) -> int:
        """获取下一个可用的 Python 脚本编号（从已有文件名推算）。"""
        existing = set()
        prefix = f'{self.module_name}_py_'
        for sc in self.script_list:
            if sc.script_type == ScriptType.PYTHON and sc.script_path:
                basename = os.path.basename(sc.script_path)
                if basename.startswith(prefix) and basename.endswith('.py'):
                    try:
                        num = int(basename[len(prefix):-3])
                        existing.add(num)
                    except ValueError:
                        pass
        n = 0
        while n in existing:
            n += 1
        return n

    def add_python_script(self) -> ScriptConfig:
        new_config = ScriptConfig.create_python_default()
        self.script_list.append(new_config)
        self.init_idx()
        num = self._next_python_script_number()
        path = os.path.join(self._get_python_scripts_dir(), f'{self.module_name}_py_{num}.py')
        new_config.script_path = path
        with open(path, 'w', encoding='utf-8') as f:
            f.write('# Python 脚本\n')
        self.save()
        return new_config

    def init_idx(self) -> None:
        """初始化下标"""
        for i in range(len(self.script_list)):
            self.script_list[i].idx = i

    def save(self):
        self.data = {
            'script_list': [i.to_dict() for i in self.script_list]
        }
        YamlConfig.save(self)

    def add_one(self) -> ScriptConfig:
        """新增一个配置并返回。

        Returns:
            新创建的 ScriptConfig。
        """
        new_config = ScriptConfig.create_default()
        self.script_list.append(new_config)
        self.init_idx()
        self.save()
        return new_config

    def delete_one(self, index: int) -> None:
        """删除一个配置。

        Args:
            index: 配置下标。
        """
        if index < 0 or index >= len(self.script_list):
            return
        del self.script_list[index]
        self.init_idx()
        self.save()

    def reorder(self, new_order: list[ScriptConfig]) -> None:
        """按新顺序重排脚本列表（用于拖拽排序）。

        Args:
            new_order: 新顺序的脚本列表。
        """
        if len(new_order) != len(self.script_list):
            return
        self.script_list = list(new_order)
        self.init_idx()
        self.save()

    def update_config(self, config: ScriptConfig) -> None:
        """更新一个配置。

        Args:
            config: 要更新的脚本配置。
        """
        if config.idx < 0 or config.idx >= len(self.script_list):
            return

        self.script_list[config.idx] = config
        self.init_idx()
        self.save()
