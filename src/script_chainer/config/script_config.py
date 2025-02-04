import os
from enum import Enum

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.config.yaml_config import YamlConfig


class CheckDoneOptions(Enum):

    SCRIPT_CLOSED = ConfigItem(label='脚本被关闭', value='script_closed')
    GAME_CLOSED = ConfigItem(label='游戏被关闭', value='game_closed')


class ScriptConfig:

    def __init__(self,
                 script_path: str,
                 script_window_title: str,
                 game_window_title: str,
                 run_timeout_seconds: int,
                 check_done: str,
                 script_arguments: str,
                 ):

        self.idx: int = 0  # 下标 由外面控制
        self.script_path: str = script_path  # 运行脚本的路径
        self.script_window_title: str = script_window_title  # 运行脚本的窗口名称
        self.game_window_title: str = game_window_title  # 运行游戏的窗口名称
        self.run_timeout_seconds: int = run_timeout_seconds  # 脚本超时时间
        self.check_done: str = check_done  # 怎么判断脚本已经运行完毕
        self.script_arguments: str = script_arguments  # 运行脚本的附加参数

    @property
    def script_display_name(self) -> str:
        if self.script_window_title is not None and len(self.script_window_title) > 0:
            return self.script_window_title
        else:
            return os.path.basename(self.script_path)


class ScriptChainConfig(YamlConfig):

    def __init__(self, module_name: str, is_mock: bool = False):
        YamlConfig.__init__(
            self,
            module_name,
            sub_dir=['script_chain'],
            is_mock=is_mock, sample=False, copy_from_sample=False,
        )

        self.script_list: list[ScriptConfig] = [
            ScriptConfig(
                script_path=i.get('script_path', ''),
                script_window_title=i.get('script_window_title', ''),
                game_window_title=i.get('game_window_title', ''),
                run_timeout_seconds=i.get('run_timeout_seconds', 3600),
                check_done=i.get('check_done', ''),
                script_arguments=i.get('script_arguments', ''),
            )
            for i in self.get('script_list', [])
        ]

    def init_idx(self) -> None:
        """
        初始化下标
        :return:
        """
        for i in range(len(self.script_list)):
            self.script_list[i].idx = i

    def save(self):
        self.data = {
            'script_list': [
                {
                    'script_path': i.script_path,
                    'script_window_title': i.script_window_title,
                    'game_window_title': i.game_window_title,
                    'run_timeout_seconds': i.run_timeout_seconds,
                    'check_done': i.check_done,
                    'script_arguments': i.script_arguments,
                }
                for i in self.script_list
           ]
        }
        YamlConfig.save(self)

    def add_one(self) -> ScriptConfig:
        """
        新增一个配置 并返回
        :return:
        """
        new_config = ScriptConfig(
            script_path='',
            script_window_title='',
            game_window_title='',
            run_timeout_seconds=3600,
            check_done='',
            script_arguments='',
        )
        self.script_list.append(new_config)
        self.init_idx()
        self.save()
        return new_config

    def delete_one(self, index: int) -> None:
        """
        删除一个配置
        :param index:
        :return:
        """
        if index < 0 or index >= len(self.script_list):
            return
        del self.script_list[index]
        self.init_idx()
        self.save()

    def move_up(self, index: int) -> None:
        """
        向上移动一个配置
        :param index:
        :return:
        """
        if index <= 0 or index >= len(self.script_list):
            return
        self.script_list[index], self.script_list[index - 1] = self.script_list[index - 1], self.script_list[index]
        self.init_idx()
        self.save()
