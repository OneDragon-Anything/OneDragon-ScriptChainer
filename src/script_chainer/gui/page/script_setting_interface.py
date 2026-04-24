import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    CaptionLabel,
    Dialog,
    DoubleSpinBox,
    FluentIcon,
    HyperlinkCard,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PrimaryDropDownPushButton,
    PushButton,
    RoundMenu,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
    TransparentToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.draggable_list import DraggableList, DraggableListItem
from one_dragon_qt.widgets.setting_card.code_editor_setting_card import (
    PythonCodeEditorDialog,
)
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.editable_combo_box_setting_card import (
    EditableComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.tag_label import TagLabel
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.config.script_config import (
    AttachDirection,
    CheckDoneMethods,
    GameProcessName,
    ScriptChainConfig,
    ScriptConfig,
    ScriptProcessName,
    ScriptType,
)
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.utils.process_utils import launch_in_terminal
from script_chainer.utils.runner_utils import (
    build_runner_command,
)


def _show_info(parent: QWidget, level: str, title: str, content: str, duration: int = 3000) -> None:
    """显示 InfoBar 通知。"""
    getattr(InfoBar, level)(
        title=title,
        content=content,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=duration,
        parent=parent,
    )


def _show_success(parent: QWidget, title: str, content: str) -> None:
    _show_info(parent, 'success', title, content)


def _show_warning(parent: QWidget, title: str, content: str) -> None:
    _show_info(parent, 'warning', title, content)


def _show_error(parent: QWidget, title: str, content: str) -> None:
    _show_info(parent, 'error', title, content, duration=5000)


class ScriptEditDialog(MessageBoxBase):
    def __init__(self, config: ScriptConfig, parent=None):
        MessageBoxBase.__init__(self, parent)
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')

        self.config: ScriptConfig = config

        self.script_path_opt = PushSettingCard(icon=FluentIcon.FOLDER, title='脚本路径', text='选择')
        self.script_path_opt.clicked.connect(self.on_script_path_clicked)
        self.viewLayout.addWidget(self.script_path_opt)

        self.script_process_name_opt = EditableComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='脚本进程名称',
            content='需要监听脚本关闭时填入',
            options_enum=ScriptProcessName,
            input_placeholder='选择或输入脚本进程名',
        )
        self.script_process_name_opt.combo_box.setFixedWidth(320)
        self.script_process_name_opt.value_changed.connect(self._on_script_process_selected)
        self.viewLayout.addWidget(self.script_process_name_opt)

        self.game_process_name_opt = EditableComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='游戏进程名称',
            content='需要监听游戏关闭时填入',
            options_enum=GameProcessName,
            input_placeholder='选择或输入游戏进程名',
        )
        self.game_process_name_opt.combo_box.setFixedWidth(320)
        self.game_process_name_opt.value_changed.connect(self._on_game_process_selected)
        self.viewLayout.addWidget(self.game_process_name_opt)

        self.run_timeout_seconds_opt = TextSettingCard(
            icon=FluentIcon.HISTORY,
            title='运行超时(秒)',
            content='超时后自动进行下一个脚本'
        )
        self.viewLayout.addWidget(self.run_timeout_seconds_opt)

        self.check_done_opt = ComboBoxSettingCard(
            icon=FluentIcon.COMPLETED,
            title='检查完成方式',
            options_enum=CheckDoneMethods,
        )
        self.viewLayout.addWidget(self.check_done_opt)

        self.kill_script_after_done_opt = SwitchSettingCard(
            icon=FluentIcon.POWER_BUTTON,
            title='结束后关闭脚本进程',
        )
        self.viewLayout.addWidget(self.kill_script_after_done_opt)

        self.kill_game_after_done_opt = SwitchSettingCard(
            icon=FluentIcon.POWER_BUTTON,
            title='结束后关闭游戏进程',
        )
        self.viewLayout.addWidget(self.kill_game_after_done_opt)

        self.script_arguments_opt = TextSettingCard(
            icon=FluentIcon.COMMAND_PROMPT,
            title='脚本启动参数',
        )
        self.script_arguments_opt.line_edit.setMinimumWidth(200)
        self.viewLayout.addWidget(self.script_arguments_opt)

        self.error_label = CaptionLabel(text="输入不正确")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        self.viewLayout.addWidget(self.error_label)

        self.notify_start_opt = SwitchSettingCard(
            icon=FluentIcon.MESSAGE,
            title='脚本开始时发送通知',
        )
        self.viewLayout.addWidget(self.notify_start_opt)

        self.notify_done_opt = SwitchSettingCard(
            icon=FluentIcon.MESSAGE,
            title='脚本结束时发送通知',
        )
        self.viewLayout.addWidget(self.notify_done_opt)

        self.notify_log_interval_input = DoubleSpinBox()
        self.notify_log_interval_input.setRange(0.5, 60)
        self.notify_log_interval_input.setSingleStep(0.5)
        self.notify_log_interval_input.setDecimals(1)
        self.notify_log_interval_input.setFixedWidth(140)

        self.notify_log_switch = SwitchButton()
        self.notify_log_switch.setOnText('')
        self.notify_log_switch.setOffText('')
        self.notify_log_switch.checkedChanged.connect(self._on_notify_log_toggled)

        self.notify_log_opt = MultiPushSettingCard(
            icon=FluentIcon.SEND,
            title='定时推送运行日志',
            content='按设定间隔（分钟）将命令行输出合并推送',
            btn_list=[self.notify_log_interval_input, self.notify_log_switch],
        )
        self.viewLayout.addWidget(self.notify_log_opt)

        # ── 静默超时重启 ──
        self.no_log_timeout_input = SpinBox()
        self.no_log_timeout_input.setRange(30, 86400)
        self.no_log_timeout_input.setSingleStep(30)
        self.no_log_timeout_input.setFixedWidth(140)

        self.no_log_timeout_switch = SwitchButton()
        self.no_log_timeout_switch.setOnText('')
        self.no_log_timeout_switch.setOffText('')
        self.no_log_timeout_switch.checkedChanged.connect(self._on_no_log_timeout_toggled)

        self.no_log_timeout_opt = MultiPushSettingCard(
            icon=FluentIcon.SYNC,
            title='无日志超时重启（秒）',
            content='超过设定秒数无日志输出时，判定为未响应并重新执行',
            btn_list=[self.no_log_timeout_input, self.no_log_timeout_switch],
        )
        self.viewLayout.addWidget(self.no_log_timeout_opt)

        self.no_log_max_retries_input = SpinBox()
        self.no_log_max_retries_input.setRange(1, 99)
        self.no_log_max_retries_input.setSingleStep(1)
        self.no_log_max_retries_input.setFixedWidth(140)

        self.no_log_max_retries_opt = MultiPushSettingCard(
            icon=FluentIcon.SYNC,
            title='最大重启次数',
            content='无日志超时时最多重启的次数',
            btn_list=[self.no_log_max_retries_input],
        )
        self.viewLayout.addWidget(self.no_log_max_retries_opt)

        self.init_by_config(config)

    def init_by_config(self, config: ScriptConfig):
        # 复制一个 防止修改了原来的
        self.config = config.copy()

        self.script_path_opt.setContent(config.script_path)
        self._set_editable_combo_value(self.script_process_name_opt, config.script_process_name)
        self._set_editable_combo_value(self.game_process_name_opt, config.game_process_name)
        self.run_timeout_seconds_opt.setValue(str(config.run_timeout_seconds), emit_signal=False)
        self.check_done_opt.setValue(config.check_done, emit_signal=False)
        self.kill_script_after_done_opt.setValue(config.kill_script_after_done, emit_signal=False)
        self.kill_game_after_done_opt.setValue(config.kill_game_after_done, emit_signal=False)
        self.script_arguments_opt.setValue(config.script_arguments, emit_signal=False)
        self.notify_start_opt.setValue(config.notify_start, emit_signal=False)
        self.notify_done_opt.setValue(config.notify_done, emit_signal=False)

        notify_log_enabled = config.notify_log_interval > 0
        self.notify_log_switch.blockSignals(True)
        self.notify_log_switch.setChecked(notify_log_enabled)
        self.notify_log_switch.blockSignals(False)
        interval_sec = config.notify_log_interval if notify_log_enabled else 300
        minutes = interval_sec / 60
        self.notify_log_interval_input.blockSignals(True)
        self.notify_log_interval_input.setValue(minutes)
        self.notify_log_interval_input.blockSignals(False)
        self.notify_log_interval_input.setEnabled(notify_log_enabled)

        no_log_enabled = config.no_log_timeout_seconds > 0
        self.no_log_timeout_switch.blockSignals(True)
        self.no_log_timeout_switch.setChecked(no_log_enabled)
        self.no_log_timeout_switch.blockSignals(False)
        self.no_log_timeout_input.blockSignals(True)
        self.no_log_timeout_input.setValue(config.no_log_timeout_seconds if no_log_enabled else 300)
        self.no_log_timeout_input.blockSignals(False)
        self.no_log_timeout_input.setEnabled(no_log_enabled)
        self.no_log_max_retries_input.blockSignals(True)
        self.no_log_max_retries_input.setValue(max(1, config.no_log_max_retries))
        self.no_log_max_retries_input.blockSignals(False)
        self.no_log_max_retries_input.setEnabled(no_log_enabled)

    def _on_notify_log_toggled(self, checked: bool) -> None:
        """日志推送开关切换时启用/禁用间隔输入框"""
        self.notify_log_interval_input.setEnabled(checked)

    def _on_no_log_timeout_toggled(self, checked: bool) -> None:
        """静默超时重启开关切换时启用/禁用相关输入框"""
        self.no_log_timeout_input.setEnabled(checked)
        self.no_log_max_retries_input.setEnabled(checked)

    @staticmethod
    def _set_editable_combo_value(card: EditableComboBoxSettingCard, value: str) -> None:
        """设置可编辑下拉框的值，若预设列表中无匹配则直接设置文本"""
        card.combo_box.blockSignals(True)
        # 先尝试匹配预设选项
        matched = False
        for idx in range(card.combo_box.count()):
            if card.combo_box.itemData(idx) == value:
                card.combo_box.setCurrentIndex(idx)
                matched = True
                break
        if not matched:
            card.combo_box.setCurrentIndex(-1)
            card.combo_box.setText(value if value else '')
        card.combo_box.blockSignals(False)

    def _on_script_process_selected(self, _idx: int, val: object) -> None:
        """脚本进程选中后，显示 value 并恢复 content"""
        self.script_process_name_opt.combo_box.setText(str(val) if val else '')
        self.script_process_name_opt.setContent('需要监听脚本关闭时填入')

    def _on_game_process_selected(self, _idx: int, val: object) -> None:
        """游戏进程选中后，显示 value 并恢复 content"""
        self.game_process_name_opt.combo_box.setText(str(val) if val else '')
        self.game_process_name_opt.setContent('需要监听游戏关闭时填入')

    def on_script_path_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择你的脚本'))
        if file_path is not None and file_path != '':
            self.on_script_path_chosen(os.path.normpath(file_path))

    def on_script_path_chosen(self, file_path) -> None:
        self.config.script_path = file_path
        self.script_path_opt.setContent(file_path)

    def _get_editable_combo_value(self, card: EditableComboBoxSettingCard) -> str:
        """获取可编辑下拉框的值，优先取 itemData，否则取用户输入的文本"""
        val = card.getValue()
        if val is not None:
            return str(val)
        return card.combo_box.currentText().strip()

    def get_config_value(self) -> ScriptConfig:
        config = self.config.copy()
        config.script_path = self.config.script_path
        config.script_process_name = self._get_editable_combo_value(self.script_process_name_opt)
        config.game_process_name = self._get_editable_combo_value(self.game_process_name_opt)
        config.run_timeout_seconds = int(self.run_timeout_seconds_opt.getValue())
        config.check_done = str(self.check_done_opt.getValue())
        config.kill_script_after_done = self.kill_script_after_done_opt.btn.isChecked()
        config.kill_game_after_done = self.kill_game_after_done_opt.btn.isChecked()
        config.script_arguments = self.script_arguments_opt.getValue()
        config.notify_start = self.notify_start_opt.btn.isChecked()
        config.notify_done = self.notify_done_opt.btn.isChecked()

        if self.notify_log_switch.isChecked():
            minutes = self.notify_log_interval_input.value()
            config.notify_log_interval = max(30, int(minutes * 60))
        else:
            config.notify_log_interval = 0

        if self.no_log_timeout_switch.isChecked():
            config.no_log_timeout_seconds = max(30, self.no_log_timeout_input.value())
        else:
            config.no_log_timeout_seconds = 0
        config.no_log_max_retries = self.no_log_max_retries_input.value()

        return config

    def validate(self) -> bool:
        """ 重写验证表单数据的方法 """
        config = self.get_config_value()
        invalid_message = config.invalid_message
        if invalid_message is not None:
            self.error_label.setText(invalid_message)
            self.error_label.show()
            return False
        else:
            self.error_label.hide()
            return True


class ScriptCardMixin:
    """脚本卡片公共逻辑 Mixin。

    提供：重命名（hover 铅笔）、开关、删除、init_by_config、after_update_item。
    子类需在 __init__ 中：
      1. 设置 self.config
      2. 调用 _setup_common_widgets() 获取 enable_switch / edit_btn / delete_btn
      3. 创建 content_widget 后调用 _setup_rename_btn(content_widget)
      4. 最后调用 _update_display()
    并实现 _update_display()。
    """

    config: ScriptConfig
    value_changed: Signal
    deleted: Signal

    # ── 公共控件创建 ──

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
        # 子类可在 titleLabel 前后插入 tag
        self._title_row.addWidget(content_widget.titleLabel)
        self._title_row.addWidget(self._rename_btn)
        self._title_row.addStretch()
        content_widget.vBoxLayout.insertLayout(0, self._title_row)

    # ── 公共事件处理 ──

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

    # ── 公共数据方法 ──

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
            _show_warning(self.window(), '配置不合法', invalid_msg)
            return

        display = self.config.script_display_name

        try:
            cmd, cwd = build_runner_command(self.chain_name, self.index)
            launch_in_terminal(
                command=cmd,
                cwd=cwd,
                title=f'调试 {display}',
            )
            _show_success(self.window(), '调试运行', f'已在终端启动 {display}')
        except Exception as e:
            _show_error(self.window(), '启动失败', str(e))

    def on_edit_clicked(self) -> None:
        """点击编辑，弹出窗口"""
        dialog = ScriptEditDialog(config=self.config,
                                  parent=self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config_value()
            self.init_by_config(config)
            self.value_changed.emit(config)

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

        # 标签插入 title_row：titleLabel [↑后置/↓前置] [外部] [rename_btn] [stretch]
        self._post_tag = TagLabel('↑ 后置', color='#E08020')
        self._pre_tag = TagLabel('↓ 前置', color='#E08020')
        self._external_tag = TagLabel('外部')

        # 状态 tag 插到 rename_btn 前面
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

    def _on_attach_up(self) -> None:
        """切换向上挂靠"""
        if self.config.attach_direction == AttachDirection.POST:
            self.config.attach_direction = AttachDirection.NONE
        else:
            if self.index <= 0:
                _show_warning(self.window(), '无法挂靠', '上方没有可挂靠的脚本')
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
                _show_warning(self.window(), '无法挂靠', '下方没有可挂靠的脚本')
                return
            self.config.attach_direction = AttachDirection.PRE
        self._update_display()
        self.value_changed.emit(self.config)
        self.attach_changed.emit()

    def on_run_clicked(self) -> None:
        """调试运行当前 Python 脚本。"""
        path = self.config.script_path
        if not path or not os.path.exists(path):
            _show_warning(self.window(), '无法运行', 'Python 脚本文件不存在')
            return

        display = self.config.script_display_name
        try:
            cmd, cwd = build_runner_command(self.chain_config.module_name, self.index)
            launch_in_terminal(
                command=cmd,
                cwd=cwd,
                title=f'调试 {display}',
            )
            _show_success(self.window(), '调试运行', f'已在终端启动 {display}')
        except Exception as e:
            _show_error(self.window(), '启动失败', str(e))

    def on_edit_clicked(self) -> None:
        """编辑 Python 脚本。外部脚本直接调用外部编辑器，内部脚本弹窗编辑。"""
        path = self.config.script_path
        if path and not self.chain_config._is_managed_script(path):
            if os.name == 'nt':
                try:
                    os.startfile(path, 'edit')
                except (AttributeError, OSError) as e:
                    _show_error(self.window(), '打开失败', f'无法打开外部脚本进行编辑：{e}')
            else:
                try:
                    if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                        raise OSError('系统默认编辑器未能打开该文件')
                except OSError as e:
                    _show_error(self.window(), '打开失败', f'无法打开外部脚本进行编辑：{e}')
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
        is_external = bool(
            self.config.script_path
            and not self.chain_config._is_managed_script(self.config.script_path)
        )
        self._external_tag.setVisible(is_external)


class ScriptSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx: ScriptChainerContext = ctx

        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='script_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='脚本链'
        )
        self.ctx: ScriptChainerContext = ctx
        self.chosen_config: ScriptChainConfig | None = None
        self._runner_launch_in_progress: bool = False

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='使用说明', text='前往',
                                      url='https://onedragon-anything.github.io/tools/zh/script_chainer.html')
        self.help_opt.setContent('先看说明 再使用与提问')
        content_widget.add_widget(self.help_opt)

        self.chain_combo_box = ComboBox()
        self.chain_combo_box.currentIndexChanged.connect(self.on_chain_selected)

        self.add_chain_btn = TransparentToolButton(FluentIcon.ADD)
        self.add_chain_btn.setToolTip('新建脚本链')
        self.add_chain_btn.clicked.connect(self.on_add_chain_clicked)
        self.rename_chain_btn = TransparentToolButton(FluentIcon.EDIT)
        self.rename_chain_btn.setToolTip('重命名')
        self.rename_chain_btn.clicked.connect(self.on_rename_chain_clicked)
        self.delete_chain_btn = TransparentToolButton(FluentIcon.DELETE)
        self.delete_chain_btn.setToolTip('删除')
        self.delete_chain_btn.clicked.connect(self.on_delete_chain_clicked)

        self.run_chain_btn = PushButton(text='运行全部', icon=FluentIcon.PLAY)
        self.run_chain_btn.clicked.connect(self.on_run_chain_clicked)
        add_script_menu = RoundMenu(parent=self)
        add_script_menu.addAction(Action(FluentIcon.APPLICATION, '外部程序', triggered=self.on_add_script_clicked))
        add_script_menu.addAction(Action(FluentIcon.CODE, '新建 Python 脚本', triggered=self.on_add_python_script_clicked))
        add_script_menu.addAction(Action(FluentIcon.DOCUMENT, '选择已有 Python 脚本', triggered=self.on_import_python_script_clicked))
        self.add_script_btn = PrimaryDropDownPushButton(text='新增脚本')
        self.add_script_btn.setMenu(add_script_menu)

        self.chain_toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.chain_toolbar)
        toolbar_layout.setContentsMargins(0, 16, 16, 8)
        toolbar_layout.setSpacing(4)
        toolbar_layout.addWidget(SubtitleLabel('脚本链'))
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.chain_combo_box)
        toolbar_layout.addWidget(self.add_chain_btn)
        toolbar_layout.addWidget(self.rename_chain_btn)
        toolbar_layout.addWidget(self.delete_chain_btn)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.run_chain_btn)
        toolbar_layout.addSpacing(4)
        toolbar_layout.addWidget(self.add_script_btn)
        content_widget.add_widget(self.chain_toolbar)

        self.script_list_widget = DraggableList()
        self.script_list_widget.order_changed.connect(self.on_order_changed)
        self.script_card_list: list[DraggableListItem] = []
        content_widget.add_widget(self.script_list_widget)

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.update_chain_combo_box()
        self.chain_combo_box.setCurrentIndex(0)
        self.update_chain_display()

    def update_chain_combo_box(self) -> None:
        """更新脚本链选项"""
        self.chain_combo_box.set_items(
            [
                ConfigItem(i.module_name)
                for i in self.ctx.get_all_script_chain_config()
            ],
            target_value=None if self.chosen_config is None else self.chosen_config.module_name
        )

    def on_chain_selected(self, index: int) -> None:
        """当选择脚本链时。

        Args:
            index: 选项下标。
        """
        module_name = self.chain_combo_box.currentData()
        self.chosen_config = ScriptChainConfig(module_name)
        self.update_chain_display()

    def on_add_chain_clicked(self) -> None:
        """新增一个脚本链"""
        config = self.ctx.add_script_chain_config()
        self.update_chain_combo_box()
        self.chain_combo_box.init_with_value(config.module_name)
        self.on_chain_selected(-1)

    def on_delete_chain_clicked(self) -> None:
        """移除一个脚本链"""
        dialog = Dialog("警告", "你确定要删除这个脚本链吗？\n删除之后无法恢复！", parent=self.window())
        dialog.setTitleBarVisible(False)
        dialog.yesButton.setText("删除")
        dialog.cancelButton.setText("取消")
        if dialog.exec():
            if self.chosen_config is not None:
                self.ctx.remove_script_chain_config(self.chosen_config)
                self.chosen_config = None
            self.update_chain_combo_box()
            self.update_chain_display()

    def on_rename_chain_clicked(self) -> None:
        """重命名脚本链"""
        if self.chosen_config is None:
            return

        dialog = ChainRenameDialog(self.chosen_config.module_name, parent=self.window())
        if dialog.exec():
            new_name = dialog.get_new_name()
            try:
                new_config = self.ctx.rename_script_chain_config(self.chosen_config, new_name)
                self.chosen_config = new_config
                self.update_chain_combo_box()
                self.chain_combo_box.init_with_value(new_name)
            except ValueError as e:
                error_dialog = Dialog("错误", str(e), parent=self.window())
                error_dialog.setTitleBarVisible(False)
                error_dialog.exec()

    def on_add_script_clicked(self) -> None:
        """新增一个脚本配置"""
        if self.chosen_config is None:
            return
        self.chosen_config.add_one()
        self.update_chain_display()

    def on_add_python_script_clicked(self) -> None:
        """新增一个 Python 脚本"""
        if self.chosen_config is None:
            return
        self.chosen_config.add_python_script()
        self.update_chain_display()

    def on_import_python_script_clicked(self) -> None:
        """选择已有的 Python 脚本文件"""
        if self.chosen_config is None:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择 Python 脚本', '', 'Python 文件 (*.py)'
        )
        if not file_path:
            return
        self.chosen_config.add_python_script_from_file(file_path)
        self.update_chain_display()

    def on_run_chain_clicked(self) -> None:
        """拉起独立 runner 运行当前脚本链。"""
        if self.chosen_config is None or self._runner_launch_in_progress:
            return

        self._runner_launch_in_progress = True
        self.run_chain_btn.setEnabled(False)
        chain_name = self.chosen_config.module_name
        try:
            cmd, cwd = build_runner_command(chain_name)
            launch_in_terminal(
                command=cmd,
                cwd=cwd,
                title=f'运行脚本链 {chain_name}',
            )
            _show_success(self.window(), '运行全部', f'已在终端启动脚本链 {chain_name}')
        except Exception as e:
            _show_error(self.window(), '启动失败', str(e))
        finally:
            self._runner_launch_in_progress = False
            self.run_chain_btn.setEnabled(True)

    def update_chain_display(self) -> None:
        """更新脚本链的显示"""
        chosen: bool = self.chosen_config is not None
        self.script_list_widget.setVisible(chosen)
        self.add_script_btn.setVisible(chosen)
        self.run_chain_btn.setVisible(chosen)
        self.rename_chain_btn.setVisible(chosen)
        self.delete_chain_btn.setVisible(chosen)

        if not chosen:
            return

        # 清空现有列表并重建
        self.script_card_list.clear()
        self.script_list_widget.clear()

        if self.chosen_config is None:
            return

        # 取消列表自带的 spacing，改用每张卡片的 margin 控制间距
        self.script_list_widget._layout.setSpacing(0)

        for i, script_config in enumerate(self.chosen_config.script_list):
            if script_config.script_type == ScriptType.PYTHON:
                card = PythonScriptSettingCard(
                    script_config, chain_config=self.chosen_config, index=i)
                card.attach_changed.connect(self._update_attach_margins)
            else:
                card = ScriptSettingCard(
                    script_config,
                    chain_name=self.chosen_config.module_name,
                    index=i,
                )
            self.script_card_list.append(card)
            self.script_list_widget.add_list_item(card)

            card.value_changed.connect(self.script_config_changed)
            card.deleted.connect(self.script_config_deleted)

        self._update_attach_margins()

    def on_order_changed(self, new_data_list: list) -> None:
        """拖拽排序后的回调。

        Args:
            new_data_list: 新顺序的数据列表。
        """
        if self.chosen_config is None:
            return

        self.chosen_config.reorder(new_data_list)

        # 记录旧位置（从旧的 script_card_list 顺序推算）
        old_index_of = {}
        for old_idx, card in enumerate(self.script_card_list):
            old_index_of[id(card.data)] = old_idx

        # 更新卡片列表的顺序和索引
        new_card_list: list[DraggableListItem] = []
        for data in new_data_list:
            for card in self.script_card_list:
                if card.data is data:
                    new_card_list.append(card)
                    break
        self.script_card_list = new_card_list

        # 计算哪些数据对象的位置发生了变化
        moved_ids = set()
        for new_idx, card in enumerate(self.script_card_list):
            if old_index_of.get(id(card.data), new_idx) != new_idx:
                moved_ids.add(id(card.data))

        for idx, card in enumerate(self.script_card_list):
            config = card.data
            if isinstance(config, ScriptConfig) and config.script_type == ScriptType.PYTHON:
                should_clear = id(config) in moved_ids
                # 挂靠目标位置变了也要清除
                if not should_clear and config.attach_direction == AttachDirection.POST and idx > 0:
                    should_clear = id(self.script_card_list[idx - 1].data) in moved_ids
                if not should_clear and config.attach_direction == AttachDirection.PRE and idx < len(self.script_card_list) - 1:
                    should_clear = id(self.script_card_list[idx + 1].data) in moved_ids
                if should_clear:
                    config.attach_direction = AttachDirection.NONE
            card.data.idx = idx
            card.update_item(card.data, idx)
        self.chosen_config.save()
        self._update_attach_margins()

    def _update_attach_margins(self) -> None:
        """根据 Python 脚本的挂靠方向更新卡片间距。

        每张卡片默认上下各 2px 间距（共 4px 间隔）。
        挂靠时取消对应方向的间距，使两张卡片紧贴。
        """
        n = len(self.script_card_list)
        # 先用 list 记录每张卡片的 top/bottom margin
        top = [4] * n
        bottom = [4] * n

        for i in range(n):
            if self.chosen_config and self.chosen_config.has_next_attached(i):
                bottom[i] = 0
                top[i + 1] = 0

        for i, card in enumerate(self.script_card_list):
            card.layout().setContentsMargins(0, top[i], 0, bottom[i])

    def script_config_changed(self, config: ScriptConfig) -> None:
        """脚本配置变化"""
        if self.chosen_config is None:
            return

        self.chosen_config.update_config(config)

    def script_config_deleted(self, idx: int) -> None:
        """脚本配置删除"""
        if self.chosen_config is None:
            return

        # 清理相邻脚本的挂靠关系，防止"漂移"到新邻居
        script_list = self.chosen_config.script_list
        if idx > 0:
            prev = script_list[idx - 1]
            if prev.script_type == ScriptType.PYTHON and prev.attach_direction == AttachDirection.PRE:
                prev.attach_direction = AttachDirection.NONE
        if idx < len(script_list) - 1:
            nxt = script_list[idx + 1]
            if nxt.script_type == ScriptType.PYTHON and nxt.attach_direction == AttachDirection.POST:
                nxt.attach_direction = AttachDirection.NONE

        self.chosen_config.delete_one(idx)
        self.update_chain_display()


class ChainRenameDialog(MessageBoxBase):
    def __init__(self, current_name: str, parent=None):
        MessageBoxBase.__init__(self, parent)
        self.yesButton.setText('重命名')
        self.cancelButton.setText('取消')
        self.current_name = current_name

        self.title = SubtitleLabel(text="重命名脚本链")
        self.viewLayout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_input = LineEdit()
        self.name_input.setPlaceholderText(current_name)
        self.name_input.setText(current_name)
        self.name_input.setFixedWidth(300)
        self.viewLayout.addWidget(self.name_input)

        self.error_label = CaptionLabel(text="输入不正确")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        self.viewLayout.addWidget(self.error_label)

    def get_new_name(self) -> str:
        return self.name_input.text().strip()

    def validate(self) -> bool:
        new_name = self.get_new_name()
        if not new_name:
            self.error_label.setText("脚本链名称不能为空")
            self.error_label.show()
            return False
        elif new_name == self.current_name:
            self.error_label.setText("新名称不能与当前名称相同")
            self.error_label.show()
            return False
        elif len(new_name) > 10:
            self.error_label.setText("脚本链名称不能超过10个字符")
            self.error_label.show()
            return False
        else:
            self.error_label.hide()
            return True


class ScriptRenameDialog(MessageBoxBase):
    def __init__(self, current_name: str, parent=None):
        MessageBoxBase.__init__(self, parent)
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')

        self.title_label = SubtitleLabel(text="自定义备注")
        self.viewLayout.addWidget(self.title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_input = LineEdit()
        self.name_input.setPlaceholderText('留空则不显示备注')
        self.name_input.setText(current_name)
        self.name_input.setFixedWidth(300)
        self.viewLayout.addWidget(self.name_input)

    def get_new_name(self) -> str:
        return self.name_input.text().strip()
