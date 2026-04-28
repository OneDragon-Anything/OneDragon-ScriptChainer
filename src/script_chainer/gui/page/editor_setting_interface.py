from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (
    ColorDialog,
    FluentIcon,
    SettingCardGroup,
    Theme,
    setTheme,
)

from one_dragon.custom.custom_config import ThemeEnum
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.theme_manager import ThemeManager
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.services.github_update_service import GithubUpdateService


class GithubUpdateRunner(QThread):

    progress_changed = Signal(float, str)
    finished = Signal(bool, str)

    def __init__(self, service: GithubUpdateService):
        QThread.__init__(self)
        self.service = service

    def run(self) -> None:
        success, message = self.service.download_and_restart(self._on_progress)
        self.finished.emit(success, message)

    def _on_progress(self, progress: float, message: str) -> None:
        self.progress_changed.emit(progress, message)


class EditorSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx: ScriptChainerContext = ctx
        self.github_update_service = GithubUpdateService(ctx)
        self.github_update_runner = GithubUpdateRunner(self.github_update_service)
        self.github_update_runner.progress_changed.connect(self._on_github_update_progress)
        self.github_update_runner.finished.connect(self._on_github_update_finished)

        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='editor_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='设置'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        content_widget.add_widget(self.get_basic_group())

        content_widget.add_stretch(1)
        return content_widget

    def get_basic_group(self) -> SettingCardGroup:
        group = SettingCardGroup('基础')

        self.theme_opt = ComboBoxSettingCard(
            icon=FluentIcon.CONSTRACT, title='界面主题',
            options_enum=ThemeEnum
        )
        self.theme_opt.value_changed.connect(self.on_theme_changed)
        group.addSettingCard(self.theme_opt)

        # 自定义主题色按钮
        self.theme_color_mode_opt = PushSettingCard(icon=FluentIcon.PALETTE, title='自定义主题色', text='选择颜色')
        self.theme_color_mode_opt.clicked.connect(self._on_custom_theme_color_clicked)
        group.addSettingCard(self.theme_color_mode_opt)

        self.github_update_opt = PushSettingCard(
            icon=FluentIcon.SYNC,
            title='程序更新',
            text='从 GitHub 更新',
            content='下载最新发布版并重启替换',
        )
        self.github_update_opt.clicked.connect(self._on_github_update_clicked)
        group.addSettingCard(self.github_update_opt)

        return group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.theme_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme'))

    def on_theme_changed(self, index: int, value: str) -> None:
        """主题改变。

        Args:
            index: 选项下标。
            value: 值。
        """
        theme = self.theme_opt.getValue()
        setTheme(Theme[theme.upper()],lazy=True)

    def _on_custom_theme_color_clicked(self) -> None:
        color = self.ctx.custom_config.theme_color
        dialog = ColorDialog(QColor(color[0], color[1], color[2]), '请选择主题色', self)
        dialog.colorChanged.connect(self._update_custom_theme_color)
        dialog.yesButton.setText('确定')
        dialog.cancelButton.setText('取消')
        dialog.exec()

    def _update_custom_theme_color(self, color: QColor) -> None:
        color_tuple = (color.red(), color.green(), color.blue())
        self.ctx.custom_config.theme_color = color_tuple
        ThemeManager.set_theme_color(color_tuple)

    def _on_github_update_clicked(self) -> None:
        if self.github_update_runner.isRunning():
            return
        self.github_update_opt.button.setEnabled(False)
        self.github_update_opt.setContent(gt('正在下载 GitHub 最新发布版...'))
        self.github_update_runner.start()

    def _on_github_update_progress(self, progress: float, message: str) -> None:
        self.github_update_opt.setContent(message)

    def _on_github_update_finished(self, success: bool, message: str) -> None:
        self.github_update_opt.setContent(message)
        if success:
            QApplication.quit()
            return
        self.github_update_opt.button.setEnabled(True)
