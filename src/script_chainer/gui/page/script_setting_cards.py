import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QHBoxLayout
from qfluentwidgets import Dialog, FluentIcon, SwitchButton, TransparentToolButton

from one_dragon.utils.os_utils import reveal_in_file_manager
from one_dragon_qt.widgets.draggable_list import DraggableListItem
from one_dragon_qt.widgets.setting_card.code_editor_setting_card import (
    PythonCodeEditorDialog,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.tag_label import TagLabel
from script_chainer.config.script_config import (
    AttachDirection,
    ScriptChainConfig,
    ScriptConfig,
)
from script_chainer.gui.page.script_setting_dialogs import ScriptRenameDialog
from script_chainer.gui.page.script_setting_utils import (
    show_error,
    show_success,
    show_warning,
)
from script_chainer.utils.process_utils import launch_in_terminal
from script_chainer.utils.runner_utils import build_runner_command


class ScriptCardMixin:
    """脚本卡片公共逻辑 Mixin。"""

    config: ScriptConfig
    value_changed: Signal
    deleted: Signal

    def _setup_common_widgets(self) -> None:
        self.enable_switch = SwitchButton()
        self.enable_switch.setOnText('')
        self.enable_switch.setOffText('')
        self.enable_switch.setChecked(self.config.enabled)
        self.enable_switch.checkedChanged.connect(self.on_enable_changed)

        self.edit_btn = TransparentToolButton(FluentIcon.EDIT)
        self.edit_btn.setToolTip('编辑')
        self.edit_btn.clicked.connect(self.on_edit_clicked)

        self.delete_btn = TransparentToolButton(FluentIcon.DELETE, None)
        self.delete_btn.setToolTip('删除')
        self.delete_btn.clicked.connect(self.on_delete_clicked)

    def _setup_rename_btn(self, content_widget: MultiPushSettingCard) -> None:
        self._rename_btn = TransparentToolButton(FluentIcon.EDIT, None)
        self._rename_btn.setFixedSize(20, 20)
        self._rename_btn.setIcon(QIcon())
        self._rename_btn.setToolTip('重命名')
        self._rename_btn.clicked.connect(self._on_rename)

        self._title_row = QHBoxLayout()
        self._title_row.setContentsMargins(0, 0, 0, 0)
        self._title_row.setSpacing(4)
        content_widget.vBoxLayout.removeWidget(content_widget.titleLabel)
        self._title_row.addWidget(content_widget.titleLabel)
        self._title_row.addWidget(self._rename_btn)
        self._title_row.addStretch()
        content_widget.vBoxLayout.insertLayout(0, self._title_row)

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._rename_btn.setIcon(FluentIcon.EDIT.icon())

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._rename_btn.setIcon(QIcon())

    def on_enable_changed(self, checked: bool) -> None:
        self.config.enabled = checked
        self.value_changed.emit(self.config)

    def on_delete_clicked(self) -> None:
        dialog = Dialog('删除脚本', f'确定要删除 {self.config.script_display_name} 吗？', parent=self.window())
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText('删除')
        dialog.cancelButton.setText('取消')
        if dialog.exec():
            self.deleted.emit(self.index)

    def _on_rename(self) -> None:
        dialog = ScriptRenameDialog(self.config.display_name, parent=self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config.display_name = dialog.get_new_name()
            self._update_display()
            self.value_changed.emit(self.config)

    def init_by_config(self, config: ScriptConfig) -> None:
        self.config = config
        self.data = config
        self._update_display()

    def after_update_item(self) -> None:
        self.config = self.data
        self._update_display()


class ScriptSettingCard(ScriptCardMixin, DraggableListItem):

    value_changed = Signal(ScriptConfig)
    deleted = Signal(int)
    edit_requested = Signal(object)

    def __init__(self, config: ScriptConfig, chain_name: str, index: int = 0, parent=None,
                 enable_opacity_effect: bool = True):
        self.config: ScriptConfig = config
        self.chain_name: str = chain_name
        self._setup_common_widgets()

        self.debug_btn = TransparentToolButton(FluentIcon.PLAY, None)
        self.debug_btn.setToolTip('调试运行')
        self.debug_btn.clicked.connect(self.on_debug_clicked)

        content_widget = MultiPushSettingCard(
            icon=FluentIcon.GAME,
            title='游戏',
            content='脚本',
            parent=parent,
            btn_list=[
                self.debug_btn,
                self.edit_btn,
                self.delete_btn,
                self.enable_switch,
            ]
        )

        self._setup_rename_btn(content_widget)

        DraggableListItem.__init__(
            self,
            data=config,
            index=index,
            content_widget=content_widget,
            parent=parent,
            enable_opacity_effect=enable_opacity_effect,
        )

        self.content_widget: MultiPushSettingCard
        self._update_display()

    def on_debug_clicked(self) -> None:
        """调试运行当前脚本"""
        invalid_msg = self.config.invalid_message
        if invalid_msg is not None:
            show_warning(self.window(), '配置不合法', invalid_msg)
            return

        display = self.config.script_display_name

        try:
            cmd, cwd = build_runner_command(self.chain_name, self.index)
            launch_in_terminal(
                command=cmd,
                cwd=cwd,
                title=f'调试 {display}',
            )
            show_success(self.window(), '调试运行', f'已在终端启动 {display}')
        except Exception as e:
            show_error(self.window(), '启动失败', str(e))

    def on_edit_clicked(self) -> None:
        """请求进入脚本编辑二级界面。"""
        self.edit_requested.emit(self)

    def _update_display(self) -> None:
        """更新卡片显示内容"""
        title = self.config.game_display_name or '外部程序'
        if self.config.display_name:
            title += f' - {self.config.display_name}'
        self.content_widget.setTitle(title)
        script_name = (
            os.path.basename(self.config.script_path)
            if self.config.script_path else '未设置'
        )
        self.content_widget.setContent(script_name)
        self.enable_switch.setChecked(self.config.enabled)


class PythonScriptSettingCard(ScriptCardMixin, DraggableListItem):
    """Python 脚本卡片，可拖拽排序，与普通脚本卡片同级。

    支持通过 ↑/↓ 按钮挂靠到相邻脚本，作为前置/后置脚本。
    挂靠后卡片间距缩小，表示依附关系。
    """

    value_changed = Signal(ScriptConfig)
    deleted = Signal(int)
    attach_changed = Signal()

    def __init__(self, config: ScriptConfig, chain_config: ScriptChainConfig,
                 index: int = 0, parent=None,
                 enable_opacity_effect: bool = True):
        self.config: ScriptConfig = config
        self.chain_config: ScriptChainConfig = chain_config
        self._setup_common_widgets()

        self.attach_up_btn = TransparentToolButton(FluentIcon.UP, None)
        self.attach_up_btn.setToolTip('挂靠到上方脚本（作为其后置脚本）')
        self.attach_up_btn.clicked.connect(self._on_attach_up)

        self.attach_down_btn = TransparentToolButton(FluentIcon.DOWN, None)
        self.attach_down_btn.setToolTip('挂靠到下方脚本（作为其前置脚本）')
        self.attach_down_btn.clicked.connect(self._on_attach_down)

        self.run_btn = TransparentToolButton(FluentIcon.PLAY, None)
        self.run_btn.setToolTip('调试运行')
        self.run_btn.clicked.connect(self.on_run_clicked)

        content_widget = MultiPushSettingCard(
            icon=FluentIcon.CODE,
            title=self._get_title(),
            content=self._get_display_name(),
            btn_list=[
                self.attach_up_btn,
                self.attach_down_btn,
                self.run_btn,
                self.edit_btn,
                self.delete_btn,
                self.enable_switch,
            ],
        )

        self._setup_rename_btn(content_widget)

        DraggableListItem.__init__(
            self, content_widget=content_widget,
            data=config, index=index,
            enable_opacity_effect=enable_opacity_effect,
            parent=parent,
        )
        self.content_widget: MultiPushSettingCard = content_widget

        self._post_tag = TagLabel('↑ 后置', color='#E08020')
        self._pre_tag = TagLabel('↓ 前置', color='#E08020')
        self._external_tag = TagLabel('外部')

        rename_idx = self._title_row.indexOf(self._rename_btn)
        self._title_row.insertWidget(rename_idx, self._external_tag)
        self._title_row.insertWidget(rename_idx, self._pre_tag)
        self._title_row.insertWidget(rename_idx, self._post_tag)

        self._update_display()

    def _get_title(self) -> str:
        if self.config.display_name:
            return self.config.display_name
        return 'Python 脚本'

    def _get_display_name(self) -> str:
        if self.config.script_path:
            return os.path.basename(self.config.script_path)
        return '(空)'

    def _is_external_script(self) -> bool:
        return bool(
            self.config.script_path
            and not self.chain_config._is_managed_script(self.config.script_path)
        )

    def _on_attach_up(self) -> None:
        """切换向上挂靠"""
        if self.config.attach_direction == AttachDirection.POST:
            self.config.attach_direction = AttachDirection.NONE
        else:
            if self.index <= 0:
                show_warning(self.window(), '无法挂靠', '上方没有可挂靠的脚本')
                return
            self.config.attach_direction = AttachDirection.POST
        self._update_display()
        self.value_changed.emit(self.config)
        self.attach_changed.emit()

    def _on_attach_down(self) -> None:
        """切换向下挂靠"""
        if self.config.attach_direction == AttachDirection.PRE:
            self.config.attach_direction = AttachDirection.NONE
        else:
            if self.index >= len(self.chain_config.script_list) - 1:
                show_warning(self.window(), '无法挂靠', '下方没有可挂靠的脚本')
                return
            self.config.attach_direction = AttachDirection.PRE
        self._update_display()
        self.value_changed.emit(self.config)
        self.attach_changed.emit()

    def on_run_clicked(self) -> None:
        """调试运行当前 Python 脚本。"""
        path = self.config.script_path
        if not path or not os.path.exists(path):
            show_warning(self.window(), '无法运行', 'Python 脚本文件不存在')
            return

        display = self.config.script_display_name
        try:
            cmd, cwd = build_runner_command(self.chain_config.module_name, self.index)
            launch_in_terminal(
                command=cmd,
                cwd=cwd,
                title=f'调试 {display}',
            )
            show_success(self.window(), '调试运行', f'已在终端启动 {display}')
        except Exception as e:
            show_error(self.window(), '启动失败', str(e))

    def on_edit_clicked(self) -> None:
        """编辑 Python 脚本。外部脚本定位到文件，内部脚本弹窗编辑。"""
        path = self.config.script_path
        if self._is_external_script():
            if not os.path.exists(path):
                show_warning(self.window(), '无法定位', '外部脚本文件不存在')
                return
            try:
                reveal_in_file_manager(path)
            except OSError as e:
                show_error(self.window(), '打开失败', f'无法在资源管理器中定位外部脚本：{e}')
            return
        code = self.chain_config.get_python_script_content(self.config.idx)
        dialog = PythonCodeEditorDialog(
            parent=self.window(),
            title='Python 脚本',
            initial_code=code,
            script_path=path,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.chain_config.save_python_script(self.config.idx, dialog.get_code())
            self._update_display()

    def _update_display(self) -> None:
        self.content_widget.setTitle(self._get_title())
        self.content_widget.setContent(self._get_display_name())
        self.enable_switch.setChecked(self.config.enabled)
        self._post_tag.setVisible(self.config.attach_direction == AttachDirection.POST)
        self._pre_tag.setVisible(self.config.attach_direction == AttachDirection.PRE)
        is_external = self._is_external_script()
        self._external_tag.setVisible(is_external)
        self.edit_btn.setIcon(FluentIcon.FOLDER.icon() if is_external else FluentIcon.EDIT.icon())
        self.edit_btn.setToolTip('定位文件' if is_external else '编辑')
