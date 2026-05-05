from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import (
    ColorDialog,
    ComboBox,
    FluentIcon,
    HyperlinkButton,
    PrimaryPushButton,
    PushButton,
    SettingCardGroup,
    Theme,
    setTheme,
)

from one_dragon.custom.custom_config import ThemeEnum
from one_dragon.envs.env_config import ProxyTypeEnum
from one_dragon.utils import os_utils
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.services.theme_manager import ThemeManager
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.services.github_update_service import GithubUpdateService


class GithubUpdateRunner(QThread):

    progress_changed = Signal(float, str)
    update_finished = Signal(bool, str)

    def __init__(self, service: GithubUpdateService, target_version: str):
        QThread.__init__(self)
        self.service = service
        self.target_version = target_version

    def run(self) -> None:
        success, message = self.service.download_and_restart(self.target_version, self._on_progress)
        self.update_finished.emit(success, message)

    def _on_progress(self, progress: float, message: str) -> None:
        self.progress_changed.emit(progress, message)


class GithubUpdateChecker(QThread):

    check_finished = Signal(bool, str, str, str)

    def __init__(self, ctx: ScriptChainerContext):
        QThread.__init__(self)
        self.ctx = ctx

    def run(self) -> None:
        try:
            latest_stable, latest_beta = self.ctx.github_update_service.get_latest_tags()
            self.check_finished.emit(True, latest_stable, latest_beta, '')
        except Exception as e:
            self.check_finished.emit(False, '', '', str(e))


class GhProxyUpdateRunner(QThread):

    update_finished = Signal(str)

    def __init__(self, ctx: ScriptChainerContext):
        QThread.__init__(self)
        self.ctx = ctx

    def run(self) -> None:
        self.ctx.gh_proxy_service.update_proxy_url()
        self.update_finished.emit(self.ctx.env_config.gh_proxy_url)


class GithubUpdateCard(MultiPushSettingCard):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx = ctx
        self.current_version = ''
        self.latest_stable_version = ''
        self.latest_beta_version = ''
        self.target_version = ''

        self.channel_combo = ComboBox()
        self.channel_combo.addItem(gt('正式版'), userData='stable')
        self.channel_combo.addItem(gt('测试版'), userData='beta')
        self.channel_combo.setCurrentIndex(0)
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)

        self.check_btn = PushButton(gt('检查'))
        self.check_btn.clicked.connect(self.check_and_update_display)

        self.update_btn = PrimaryPushButton(text=gt('更新'))
        self.update_btn.clicked.connect(self._on_update_clicked)

        self.version_checker = GithubUpdateChecker(ctx)
        self.version_checker.check_finished.connect(self._on_version_check_finished)

        self.update_runner: GithubUpdateRunner | None = None

        MultiPushSettingCard.__init__(
            self,
            btn_list=[self.channel_combo, self.check_btn, self.update_btn],
            icon=FluentIcon.SYNC,
            title='程序更新',
            content='检查中...',
            parent=parent,
        )
        self.check_and_update_display()

    def check_and_update_display(self) -> None:
        if self.version_checker.isRunning() or self._is_update_running():
            return

        self.setContent(gt('正在检查 GitHub 最新版本...'))
        self.channel_combo.setDisabled(True)
        self.check_btn.setDisabled(True)
        self.update_btn.setDisabled(True)
        self.update_btn.setText(gt('检查中'))
        self.version_checker.start()

    def _on_version_check_finished(
        self,
        success: bool,
        latest_stable_version: str,
        latest_beta_version: str,
        message: str,
    ) -> None:
        self.channel_combo.setEnabled(True)
        self.check_btn.setEnabled(True)

        if not success:
            self.latest_stable_version = ''
            self.latest_beta_version = ''
            self.target_version = ''
            self.setContent(f"{gt('检查更新失败')}: {message}")
            self.update_btn.setText(gt('重试'))
            self.update_btn.setDisabled(True)
            return

        self.current_version = self._current_version()
        self.latest_stable_version = latest_stable_version
        self.latest_beta_version = latest_beta_version
        self._update_display_by_channel()

    def _on_channel_changed(self, _index: int) -> None:
        if self.version_checker.isRunning() or self._is_update_running():
            return
        self._update_display_by_channel()

    def _update_display_by_channel(self) -> None:
        channel = self.channel_combo.currentData()
        channel_name = gt('测试版') if channel == 'beta' else gt('正式版')
        self.target_version = self.latest_beta_version if channel == 'beta' else self.latest_stable_version

        if not self.target_version:
            self.setContent(f"{channel_name}{gt('暂无可用版本')}")
            self.update_btn.setText(gt('不可用'))
            self.update_btn.setDisabled(True)
            return

        if not os_utils.run_in_exe():
            self.setContent(
                f"{gt('当前版本')}: {self.current_version}; "
                f"{channel_name}: {self.target_version}; "
                f"{gt('当前不是发布版，无法自动更新')}"
            )
            self.update_btn.setText(gt('不可用'))
            self.update_btn.setDisabled(True)
        elif self.current_version == self.target_version:
            self.setContent(f"{gt('已是最新版本')} {self.current_version}")
            self.update_btn.setText(gt('已最新'))
            self.update_btn.setDisabled(True)
        else:
            self.setContent(
                f"{gt('可更新')} {gt('当前版本')}: {self.current_version}; "
                f"{channel_name}: {self.target_version}"
            )
            self.update_btn.setText(gt('更新'))
            self.update_btn.setEnabled(True)

    def _on_update_clicked(self) -> None:
        if self._is_update_running():
            return

        self.channel_combo.setDisabled(True)
        self.check_btn.setDisabled(True)
        self.update_btn.setDisabled(True)
        self.update_btn.setText(gt('更新中'))
        self.setContent(gt('正在准备 GitHub 更新...'))
        self.update_runner = GithubUpdateRunner(self.ctx.github_update_service, self.target_version)
        self.update_runner.progress_changed.connect(self._on_update_progress)
        self.update_runner.update_finished.connect(self._on_update_finished)
        self.update_runner.start()

    def _on_update_progress(self, progress: float, message: str) -> None:
        if progress > 0:
            self.setContent(f'{message} {progress:.0%}')
        else:
            self.setContent(message)

    def _on_update_finished(self, success: bool, message: str) -> None:
        self.setContent(message)
        if success:
            self.update_btn.setText(gt('重启中'))
            QApplication.quit()
            return

        self.channel_combo.setEnabled(True)
        self.check_btn.setEnabled(True)
        self.update_btn.setText(gt('重试'))
        self.update_btn.setEnabled(True)

    def _is_update_running(self) -> bool:
        return self.update_runner is not None and self.update_runner.isRunning()

    def _current_version(self) -> str:
        from one_dragon.version import __version__

        return __version__


class EditorSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx: ScriptChainerContext = ctx
        self.gh_proxy_update_runner = GhProxyUpdateRunner(ctx)
        self.gh_proxy_update_runner.update_finished.connect(self._on_gh_proxy_update_finished)

        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='editor_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='设置'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        content_widget.add_widget(self.get_appearance_group())
        content_widget.add_widget(self.get_update_group())

        content_widget.add_stretch(1)
        return content_widget

    def get_appearance_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt('外观'))

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

        return group

    def get_update_group(self) -> SettingCardGroup:
        group = SettingCardGroup(gt('更新'))

        self.github_update_opt = GithubUpdateCard(self.ctx)
        group.addSettingCard(self.github_update_opt)

        self.proxy_type_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='网络代理',
            options_enum=ProxyTypeEnum,
        )
        self.proxy_type_opt.value_changed.connect(self._on_proxy_type_changed)
        group.addSettingCard(self.proxy_type_opt)

        self.personal_proxy_input = TextSettingCard(
            icon=FluentIcon.WIFI,
            title='个人代理',
            input_placeholder='http://127.0.0.1:8080',
        )
        self.personal_proxy_input.value_changed.connect(self._on_proxy_changed)
        group.addSettingCard(self.personal_proxy_input)

        self.gh_proxy_url_opt = TextSettingCard(
            icon=FluentIcon.GLOBE,
            title='GitHub 代理',
        )
        group.addSettingCard(self.gh_proxy_url_opt)

        self.auto_fetch_gh_proxy_url_opt = SwitchSettingCard(
            icon=FluentIcon.SYNC,
            title='自动获取免费代理地址',
            content='获取失败时 可前往 https://ghproxy.link/ 查看自行更新',
        )
        self.fetch_gh_proxy_url_btn = PushButton(gt('获取'), self)
        self.fetch_gh_proxy_url_btn.clicked.connect(self.on_fetch_gh_proxy_url_clicked)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addWidget(
            self.fetch_gh_proxy_url_btn,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addSpacing(16)

        self.goto_gh_proxy_link_btn = HyperlinkButton('https://ghproxy.link', gt('前往'), self)
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addWidget(
            self.goto_gh_proxy_link_btn,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        self.auto_fetch_gh_proxy_url_opt.hBoxLayout.addSpacing(16)

        group.addSettingCard(self.auto_fetch_gh_proxy_url_opt)

        return group

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.theme_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme'))
        self.proxy_type_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('proxy_type'))
        self.personal_proxy_input.init_with_adapter(self.ctx.env_config.get_prop_adapter('personal_proxy'))
        self.gh_proxy_url_opt.init_with_adapter(self.ctx.env_config.get_prop_adapter('gh_proxy_url'))
        self.auto_fetch_gh_proxy_url_opt.init_with_adapter(
            self.ctx.env_config.get_prop_adapter('auto_fetch_gh_proxy_url')
        )
        self.update_proxy_ui()
        self.refresh_gh_proxy_url_by_config()

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

    def _on_proxy_type_changed(self, index: int, value: str) -> None:
        self.update_proxy_ui()
        self._on_proxy_changed()

    def _on_proxy_changed(self) -> None:
        self.ctx.env_config.init_system_proxy()

    def on_fetch_gh_proxy_url_clicked(self) -> None:
        self.start_gh_proxy_url_refresh()

    def refresh_gh_proxy_url_by_config(self) -> None:
        if not self.ctx.env_config.auto_fetch_gh_proxy_url:
            return
        if self.ctx.env_config.proxy_type != ProxyTypeEnum.GHPROXY.value.value:
            return
        self.start_gh_proxy_url_refresh()

    def start_gh_proxy_url_refresh(self) -> None:
        if self.gh_proxy_update_runner.isRunning():
            return
        self.fetch_gh_proxy_url_btn.setDisabled(True)
        self.gh_proxy_update_runner.start()

    def _on_gh_proxy_update_finished(self, _proxy_url: str) -> None:
        self.gh_proxy_url_opt.setValue(_proxy_url, emit_signal=False)
        self.fetch_gh_proxy_url_btn.setEnabled(True)

    def update_proxy_ui(self) -> None:
        if self.ctx.env_config.proxy_type == ProxyTypeEnum.GHPROXY.value.value:
            self.personal_proxy_input.hide()
            self.gh_proxy_url_opt.show()
            self.auto_fetch_gh_proxy_url_opt.show()
        elif self.ctx.env_config.proxy_type == ProxyTypeEnum.PERSONAL.value.value:
            self.personal_proxy_input.show()
            self.gh_proxy_url_opt.hide()
            self.auto_fetch_gh_proxy_url_opt.hide()
        elif self.ctx.env_config.proxy_type == ProxyTypeEnum.NONE.value.value:
            self.personal_proxy_input.hide()
            self.gh_proxy_url_opt.hide()
            self.auto_fetch_gh_proxy_url_opt.hide()
