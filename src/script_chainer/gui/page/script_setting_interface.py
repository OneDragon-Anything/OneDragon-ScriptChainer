import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QFileDialog, QWidget
from qfluentwidgets import (
    CaptionLabel,
    Dialog,
    FluentIcon,
    HyperlinkCard,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.draggable_list import DraggableList, DraggableListItem
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
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.config.script_config import (
    CheckDoneMethods,
    GameProcessName,
    ScriptChainConfig,
    ScriptConfig,
    ScriptProcessName,
)
from script_chainer.context.script_chainer_context import ScriptChainerContext


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
            content='如果开启 则会在脚本开始时发送通知'
        )
        self.viewLayout.addWidget(self.notify_start_opt)

        self.notify_done_opt = SwitchSettingCard(
            icon=FluentIcon.MESSAGE,
            title='脚本结束时发送通知',
            content='如果开启 则会在脚本结束时发送通知'
        )
        self.viewLayout.addWidget(self.notify_done_opt)

        self.init_by_config(config)

    def init_by_config(self, config: ScriptConfig):
        # 复制一个 防止修改了原来的
        self.config = ScriptConfig(
            script_path=config.script_path,
            script_process_name=config.script_process_name,
            game_process_name=config.game_process_name,
            run_timeout_seconds=config.run_timeout_seconds,
            check_done=config.check_done,
            kill_game_after_done=config.kill_game_after_done,
            kill_script_after_done=config.kill_script_after_done,
            script_arguments=config.script_arguments,
            notify_start=config.notify_start,
            notify_done=config.notify_done,
        )
        self.config.idx = config.idx

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
            return val
        return card.combo_box.currentText().strip()

    def get_config_value(self) -> ScriptConfig:
        config = ScriptConfig(
            script_path=self.script_path_opt.contentLabel.text(),
            script_process_name=self._get_editable_combo_value(self.script_process_name_opt),
            game_process_name=self._get_editable_combo_value(self.game_process_name_opt),
            run_timeout_seconds=int(self.run_timeout_seconds_opt.getValue()),
            check_done=self.check_done_opt.getValue(),
            kill_script_after_done=self.kill_script_after_done_opt.btn.isChecked(),
            kill_game_after_done=self.kill_game_after_done_opt.btn.isChecked(),
            script_arguments=self.script_arguments_opt.getValue(),
            notify_start=self.notify_start_opt.btn.isChecked(),
            notify_done=self.notify_done_opt.btn.isChecked(),
        )
        config.idx = self.config.idx

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


class ScriptSettingCard(DraggableListItem):

    value_changed = Signal(ScriptConfig)
    deleted = Signal(int)

    def __init__(self, config: ScriptConfig, index: int = 0, parent=None,
                 enable_opacity_effect: bool = True):
        self.config: ScriptConfig = config

        self.edit_btn: PushButton = PushButton(text='编辑')
        self.edit_btn.clicked.connect(self.on_edit_clicked)

        self.delete_btn: PushButton = PushButton(text='删除')
        self.delete_btn.clicked.connect(self.on_delete_clicked)

        content_widget = MultiPushSettingCard(
            icon=FluentIcon.SETTING,
            title='游戏',
            content='脚本',
            parent=parent,
            btn_list=[
                self.edit_btn,
                self.delete_btn,
            ]
        )

        DraggableListItem.__init__(
            self,
            data=config,
            index=index,
            content_widget=content_widget,
            parent=parent,
            enable_opacity_effect=enable_opacity_effect,
        )

        self._update_display()

    def on_edit_clicked(self) -> None:
        """
        点击编辑 弹出窗口
        :return:
        """
        dialog = ScriptEditDialog(config=self.config,
                                  parent=self.window())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config_value()
            self.init_by_config(config)
            self.value_changed.emit(config)

    def init_by_config(self, config: ScriptConfig) -> None:
        """
        根据配置初始化
        :param config:
        :return:
        """
        self.config = config
        self.data = config
        self._update_display()

    def _update_display(self) -> None:
        """更新卡片显示内容"""
        self.content_widget.setTitle(f'游戏 {self.config.game_display_name}')
        self.content_widget.setContent(f'脚本 {self.config.script_display_name}')

    def after_update_item(self) -> None:
        """DraggableListItem 更新后的钩子"""
        self.config = self.data
        self._update_display()

    def on_delete_clicked(self) -> None:
        """
        删除
        """
        self.deleted.emit(self.index)


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

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='使用说明', text='前往',
                                      url='https://onedragon-anything.github.io/tools/zh/script_chainer.html')
        self.help_opt.setContent('先看说明 再使用与提问')
        content_widget.add_widget(self.help_opt)

        self.chain_combo_box = ComboBox()
        self.chain_combo_box.currentIndexChanged.connect(self.on_chain_selected)
        self.add_chain_btn: PushButton = PrimaryPushButton(text='新增')
        self.add_chain_btn.clicked.connect(self.on_add_chain_clicked)
        self.rename_chain_btn: PushButton = PushButton(text='重命名')
        self.rename_chain_btn.clicked.connect(self.on_rename_chain_clicked)
        self.delete_chain_btn: PushButton = PushButton(text='删除')
        self.delete_chain_btn.clicked.connect(self.on_delete_chain_clicked)
        self.chain_opt = MultiPushSettingCard(
            icon=FluentIcon.SETTING,
            title='脚本链',
            btn_list=[
                self.chain_combo_box,
                self.add_chain_btn,
                self.rename_chain_btn,
                self.delete_chain_btn,
            ]
        )
        content_widget.add_widget(self.chain_opt)

        self.script_list_widget = DraggableList()
        self.script_list_widget.order_changed.connect(self.on_order_changed)
        self.script_card_list: list[ScriptSettingCard] = []
        content_widget.add_widget(self.script_list_widget)

        self.add_script_btn = PrimaryPushButton(text='增加脚本')
        self.add_script_btn.clicked.connect(self.on_add_script_clicked)
        content_widget.add_widget(self.add_script_btn)

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.update_chain_combo_box()
        self.chain_combo_box.setCurrentIndex(0)
        self.update_chain_display()

    def update_chain_combo_box(self) -> None:
        """
        更新脚本链选项
        :return:
        """
        self.chain_combo_box.set_items(
            [
                ConfigItem(i.module_name)
                for i in self.ctx.get_all_script_chain_config()
            ],
            target_value=None if self.chosen_config is None else self.chosen_config.module_name
        )

    def on_chain_selected(self, index: int) -> None:
        """
        当选择脚本链时
        :param index:
        :return:
        """
        module_name = self.chain_combo_box.currentData()
        self.chosen_config = ScriptChainConfig(module_name)
        self.update_chain_display()

    def on_add_chain_clicked(self) -> None:
        """
        新增一个脚本链
        :return:
        """
        config = self.ctx.add_script_chain_config()
        self.update_chain_combo_box()
        self.chain_combo_box.init_with_value(config.module_name)
        self.on_chain_selected(-1)

    def on_delete_chain_clicked(self) -> None:
        """
        移除一个脚本链
        :return:
        """
        dialog = Dialog("警告", "你确定要删除这个脚本链吗？\n删除之后无法恢复！", parent=self.window())
        dialog.setTitleBarVisible(False)
        if dialog.exec():
            self.ctx.remove_script_chain_config(self.chosen_config)
            self.chosen_config = None
            self.update_chain_combo_box()
            self.update_chain_display()

    def on_rename_chain_clicked(self) -> None:
        """
        重命名脚本链
        :return:
        """
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
        """
        新增一个脚本配置
        :return:
        """
        if self.chosen_config is None:
            return
        self.chosen_config.add_one()
        self.update_chain_display()

    def update_chain_display(self) -> None:
        """
        更新脚本链的显示
        :return:
        """
        chosen: bool = self.chosen_config is not None
        self.script_list_widget.setVisible(chosen)
        self.add_script_btn.setVisible(chosen)
        self.rename_chain_btn.setVisible(chosen)
        self.delete_chain_btn.setVisible(chosen)

        if not chosen:
            return

        # 清空现有列表并重建
        self.script_card_list.clear()
        self.script_list_widget.clear()

        for i, script_config in enumerate(self.chosen_config.script_list):
            card = ScriptSettingCard(script_config, index=i)
            self.script_card_list.append(card)
            self.script_list_widget.add_list_item(card)

            # 移除卡片的 margins，使列表项之间紧凑
            card.layout().setContentsMargins(0, 0, 0, 0)

            card.value_changed.connect(self.script_config_changed)
            card.deleted.connect(self.script_config_deleted)

    def on_order_changed(self, new_data_list: list) -> None:
        """
        拖拽排序后的回调
        :param new_data_list: 新顺序的数据列表
        """
        if self.chosen_config is None:
            return

        self.chosen_config.reorder(new_data_list)

        # 更新卡片列表的顺序和索引
        new_card_list: list[ScriptSettingCard] = []
        for data in new_data_list:
            for card in self.script_card_list:
                if card.data is data:
                    new_card_list.append(card)
                    break
        self.script_card_list = new_card_list
        for idx, card in enumerate(self.script_card_list):
            card.config.idx = idx
            card.update_item(card.config, idx)

    def script_config_changed(self, config: ScriptConfig) -> None:
        """
        脚本配置变化
        """
        if self.chosen_config is None:
            return

        self.chosen_config.update_config(config)

    def script_config_deleted(self, idx: int) -> None:
        """
        脚本配置删除
        """
        if self.chosen_config is None:
            return

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
