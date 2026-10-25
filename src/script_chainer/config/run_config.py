from one_dragon.base.config.yaml_config import YamlConfig


class RunConfig(YamlConfig):
    """千机链专有的运行行为配置，落在 `config/run.yml`。"""

    def __init__(self, is_mock: bool = False):
        YamlConfig.__init__(
            self,
            'run',
            is_mock=is_mock, sample=False, copy_from_sample=False,
        )

    @property
    def privacy_screen_close_key(self) -> str:
        """隐私屏开关热键的主键（修饰键固定为 Ctrl+Alt+Shift）。"""
        return self.get('privacy_screen_close_key', 'f12')

    @privacy_screen_close_key.setter
    def privacy_screen_close_key(self, new_value: str) -> None:
        self.update('privacy_screen_close_key', new_value)
