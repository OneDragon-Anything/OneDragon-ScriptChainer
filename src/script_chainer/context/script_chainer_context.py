import os

from one_dragon.base.operation.one_dragon_custom_context import OneDragonCustomContext
from one_dragon.base.operation.one_dragon_env_context import OneDragonEnvContext
from one_dragon.utils import os_utils
from script_chainer.config.script_config import ScriptChainConfig


class ScriptChainerContext(OneDragonEnvContext, OneDragonCustomContext):

    def __init__(self):
        OneDragonEnvContext.__init__(self)
        OneDragonCustomContext.__init__(self)

    def get_all_script_chain_config(self) -> list[ScriptChainConfig]:
        config_list: list[ScriptChainConfig] = []
        config_dir = self.script_chain_config_dir()
        for file_name in os.listdir(config_dir):
            if not file_name.endswith('.yml'):
                continue
            config = ScriptChainConfig(module_name=file_name[:-4])
            config_list.append(config)

        return config_list

    def script_chain_config_dir(self) -> str:
        return os_utils.get_path_under_work_dir('config', 'script_chain')

    def add_script_chain_config(self) -> ScriptChainConfig:
        """
        新增一个脚本链配置 并返回
        :return:
        """
        config_dir = self.script_chain_config_dir()
        for i in range(1, 100):
            module_name = '%02d' % i
            file_name = f'{module_name}.yml'
            file_path = os.path.join(config_dir, file_name)
            if not os.path.exists(file_path):
                config = ScriptChainConfig(module_name=module_name)
                config.save()
                return config
