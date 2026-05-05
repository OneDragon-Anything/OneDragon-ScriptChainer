import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    DoubleSpinBox,
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
)

from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import (
    MultiPushSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.setting_card.value_display_editable_combo_box_setting_card import (
    ValueDisplayEditableComboBoxSettingCard,
)
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.config.script_config import (
    CheckDoneMethods,
    GameProcessName,
    ScriptConfig,
    ScriptProcessName,
)


class ScriptEditInterface(VerticalScrollInterface):

    saved = Signal(ScriptConfig)
    canceled = Signal()

    def __init__(self, config: ScriptConfig, parent=None):
        self.config: ScriptConfig = config
        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.EDIT,
            object_name='script_edit_interface',
            content_widget=None,
            parent=parent,
            nav_text_cn='编辑脚本',
        )

    def get_fixed_top_widget(self) -> QWidget | None:
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 8, 16, 8)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addWidget(SubtitleLabel('编辑脚本'))
        toolbar_layout.addStretch(1)

        self.cancel_btn = PushButton(text='取消', icon=FluentIcon.CANCEL)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        toolbar_layout.addWidget(self.cancel_btn)

        self.save_btn = PrimaryPushButton(text='保存', icon=FluentIcon.SAVE)
        self.save_btn.clicked.connect(self.on_save_clicked)
        toolbar_layout.addWidget(self.save_btn)

        return toolbar

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.script_path_opt = PushSettingCard(icon=FluentIcon.FOLDER, title='脚本路径', text='选择')
        self.script_path_opt.clicked.connect(self.on_script_path_clicked)
        content_widget.add_widget(self.script_path_opt)

        self.script_process_name_opt = ValueDisplayEditableComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='脚本进程名称',
            content='需要监听脚本关闭时填入',
            options_enum=ScriptProcessName,
            input_placeholder='选择或输入脚本进程名',
        )
        content_widget.add_widget(self.script_process_name_opt)

        self.game_process_name_opt = ValueDisplayEditableComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='游戏进程名称',
            content='需要监听游戏关闭时填入',
            options_enum=GameProcessName,
            input_placeholder='选择或输入游戏进程名',
        )
        content_widget.add_widget(self.game_process_name_opt)

        self.run_timeout_seconds_opt = TextSettingCard(
            icon=FluentIcon.HISTORY,
            title='运行超时（秒）',
            content='超时后自动进行下一个脚本'
        )
        content_widget.add_widget(self.run_timeout_seconds_opt)

        self.check_done_opt = ComboBoxSettingCard(
            icon=FluentIcon.COMPLETED,
            title='检查完成方式',
            options_enum=CheckDoneMethods,
        )
        content_widget.add_widget(self.check_done_opt)

        kill_script_switch_widget, self.kill_script_after_done_switch = self._create_switch_option('脚本')
        kill_game_switch_widget, self.kill_game_after_done_switch = self._create_switch_option('游戏')
        self.kill_after_done_opt = MultiPushSettingCard(
            icon=FluentIcon.POWER_BUTTON,
            title='结束后关闭进程',
            content='脚本结束后自动关闭对应进程',
            btn_list=[kill_script_switch_widget, kill_game_switch_widget],
        )
        content_widget.add_widget(self.kill_after_done_opt)

        self.script_arguments_opt = TextSettingCard(
            icon=FluentIcon.COMMAND_PROMPT,
            title='脚本启动参数',
        )
        self.script_arguments_opt.line_edit.setMinimumWidth(200)
        content_widget.add_widget(self.script_arguments_opt)

        self.error_label = CaptionLabel(text="输入不正确")
        self.error_label.setTextColor("#cf1010", QColor(255, 28, 32))
        self.error_label.hide()
        content_widget.add_widget(self.error_label)

        notify_start_switch_widget, self.notify_start_switch = self._create_switch_option('开始')
        notify_done_switch_widget, self.notify_done_switch = self._create_switch_option('结束')
        self.notify_opt = MultiPushSettingCard(
            icon=FluentIcon.MESSAGE,
            title='发送通知',
            content='在脚本开始或结束时发送通知',
            btn_list=[notify_start_switch_widget, notify_done_switch_widget],
        )
        content_widget.add_widget(self.notify_opt)

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
        content_widget.add_widget(self.notify_log_opt)

        self.no_log_timeout_input = SpinBox()
        self.no_log_timeout_input.setRange(1, 86400)
        self.no_log_timeout_input.setSingleStep(1)
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
        content_widget.add_widget(self.no_log_timeout_opt)

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
        content_widget.add_widget(self.no_log_max_retries_opt)

        self.init_by_config(self.config)
        return content_widget

    def on_save_clicked(self) -> None:
        if not self.validate():
            return
        self.saved.emit(self.get_config_value())

    def on_cancel_clicked(self) -> None:
        self.canceled.emit()

    @staticmethod
    def _create_switch_option(text: str) -> tuple[QWidget, SwitchButton]:
        switch = SwitchButton()
        switch.setOnText('')
        switch.setOffText('')

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(CaptionLabel(text))
        layout.addWidget(switch)
        return widget, switch

    def init_by_config(self, config: ScriptConfig):
        # 复制一个 防止修改了原来的
        self.config = config.copy()

        self.script_path_opt.setContent(config.script_path)
        self.script_process_name_opt.setValue(config.script_process_name, emit_signal=False)
        self.game_process_name_opt.setValue(config.game_process_name, emit_signal=False)
        self.run_timeout_seconds_opt.setValue(str(config.run_timeout_seconds), emit_signal=False)
        self.check_done_opt.setValue(config.check_done, emit_signal=False)
        self.kill_script_after_done_switch.setChecked(config.kill_script_after_done)
        self.kill_game_after_done_switch.setChecked(config.kill_game_after_done)
        self.script_arguments_opt.setValue(config.script_arguments, emit_signal=False)
        self.notify_start_switch.setChecked(config.notify_start)
        self.notify_done_switch.setChecked(config.notify_done)

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

    def on_script_path_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择你的脚本'))
        if file_path is not None and file_path != '':
            self.on_script_path_chosen(os.path.normpath(file_path))

    def on_script_path_chosen(self, file_path) -> None:
        self.config.script_path = file_path
        self.script_path_opt.setContent(file_path)

    def _get_editable_combo_value(self, card: ValueDisplayEditableComboBoxSettingCard) -> str:
        """获取可编辑下拉框的值，优先取 itemData，否则取用户输入的文本"""
        val = card.getValue()
        return '' if val is None else str(val).strip()

    def get_config_value(self) -> ScriptConfig:
        config = self.config.copy()
        config.script_path = self.config.script_path
        config.script_process_name = self._get_editable_combo_value(self.script_process_name_opt)
        config.game_process_name = self._get_editable_combo_value(self.game_process_name_opt)
        config.run_timeout_seconds = int(self.run_timeout_seconds_opt.getValue())
        config.check_done = str(self.check_done_opt.getValue())
        config.kill_script_after_done = self.kill_script_after_done_switch.isChecked()
        config.kill_game_after_done = self.kill_game_after_done_switch.isChecked()
        config.script_arguments = self.script_arguments_opt.getValue()
        config.notify_start = self.notify_start_switch.isChecked()
        config.notify_done = self.notify_done_switch.isChecked()

        if self.notify_log_switch.isChecked():
            minutes = self.notify_log_interval_input.value()
            config.notify_log_interval = max(30, int(minutes * 60))
        else:
            config.notify_log_interval = 0

        if self.no_log_timeout_switch.isChecked():
            config.no_log_timeout_seconds = max(1, self.no_log_timeout_input.value())
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
