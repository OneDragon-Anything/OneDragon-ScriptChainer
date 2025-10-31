import os
import threading
from concurrent.futures import ThreadPoolExecutor

from one_dragon.utils import os_utils
from one_dragon.base.push.push_service import PushService
from one_dragon.custom.custom_config import CustomConfig
from one_dragon.envs.project_config import ProjectConfig
from one_dragon.utils.log_utils import log
from script_chainer.config.script_config import ScriptChainConfig

ONE_DRAGON_CONTEXT_EXECUTOR = ThreadPoolExecutor(thread_name_prefix='one_dragon_context', max_workers=1)


class ScriptChainerContext:

    def __init__(self):
        self.project_config: ProjectConfig = ProjectConfig()
        self.custom_config: CustomConfig = CustomConfig()
        self.push_service: PushService = PushService(self)
        self._init_lock = threading.Lock()

    def init(self) -> None:
        if not self._init_lock.acquire(blocking=False):
            return

        try:
            self.push_service.init_push_channels()
        except Exception:
            log.error('初始化出错', exc_info=True)
        finally:
            self._init_lock.release()

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

    def remove_script_chain_config(self, config: ScriptChainConfig) -> None:
        """
        删除脚本链配置
        :param config:
        :return:
        """
        file_path = os.path.join(self.script_chain_config_dir(), f'{config.module_name}.yml')
        if os.path.exists(file_path):
            os.remove(file_path)

    def rename_script_chain_config(self, old_config: ScriptChainConfig, new_module_name: str) -> ScriptChainConfig:
        """
        重命名脚本链配置
        :param old_config: 原配置
        :param new_module_name: 新的模块名称
        :return: 新的配置对象
        """
        config_dir = self.script_chain_config_dir()
        old_file_path = os.path.join(config_dir, f'{old_config.module_name}.yml')
        new_file_path = os.path.join(config_dir, f'{new_module_name}.yml')

        if os.path.exists(new_file_path):
            raise ValueError(f'脚本链 {new_module_name} 已存在')

        # 创建新配置
        new_config = ScriptChainConfig(module_name=new_module_name)
        new_config.script_list = old_config.script_list.copy()
        new_config.save()

        # 删除旧配置文件
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

        return new_config

    def after_app_shutdown(self) -> None:
        """
        App关闭后进行的操作 关闭一切可能资源操作
        @return:
        """
        ONE_DRAGON_CONTEXT_EXECUTOR.shutdown(wait=False, cancel_futures=True)
