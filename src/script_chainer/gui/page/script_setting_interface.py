import os
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QFileDialog
from PySide6.QtWidgets import QWidget
from qfluentwidgets import SettingCardGroup, FluentIcon, PushButton, PrimaryPushButton, MessageBoxBase, HyperlinkCard, \
    CaptionLabel

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.setting_card.switch_setting_card import SwitchSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.config.script_config import ScriptChainConfig, ScriptConfig, GameProcessName, CheckDoneMethods, \
    ScriptProcessName
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

        self.script_process_name_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='脚本进程名称',
            content='需要监听脚本关闭时填入',
            options_enum=ScriptProcessName,
            with_custom_input=True,
        )
        self.viewLayout.addWidget(self.script_process_name_opt)

        self.game_process_name_opt = ComboBoxSettingCard(
            icon=FluentIcon.GAME,
            title='游戏进程名称',
            content='需要监听游戏关闭时填入',
            options_enum=GameProcessName,
            with_custom_input=True,
        )
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
        )
        self.config.idx = config.idx

        self.script_path_opt.setContent(config.script_path)
        self.script_process_name_opt.setValue(config.script_process_name, emit_signal=False)
        self.game_process_name_opt.setValue(config.game_process_name, emit_signal=False)
        self.run_timeout_seconds_opt.setValue(str(config.run_timeout_seconds), emit_signal=False)
        self.check_done_opt.setValue(config.check_done, emit_signal=False)
        self.kill_script_after_done_opt.setValue(config.kill_script_after_done, emit_signal=False)
        self.kill_game_after_done_opt.setValue(config.kill_game_after_done, emit_signal=False)
        self.script_arguments_opt.setValue(config.script_arguments, emit_signal=False)

    def on_script_path_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择你的脚本'))
        if file_path is not None and file_path != '':
            self.on_script_path_chosen(os.path.normpath(file_path))

    def on_script_path_chosen(self, file_path) -> None:
        self.config.script_path = file_path
        self.script_path_opt.setContent(file_path)

    def get_config_value(self) -> ScriptConfig:
        config = ScriptConfig(
            script_path=self.script_path_opt.contentLabel.text(),
            script_process_name=self.script_process_name_opt.getValue(),
            game_process_name=self.game_process_name_opt.getValue(),
            run_timeout_seconds=int(self.run_timeout_seconds_opt.get_value()),
            check_done=self.check_done_opt.getValue(),
            kill_script_after_done=self.kill_script_after_done_opt.get_value(),
            kill_game_after_done=self.kill_game_after_done_opt.get_value(),
            script_arguments=self.script_arguments_opt.get_value(),
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


class ScriptSettingCard(MultiPushSettingCard):

    value_changed = Signal(ScriptConfig)
    move_up = Signal(int)
    deleted = Signal(int)

    def __init__(self, config: ScriptConfig, parent=None):
        self.edit_btn: PushButton = PushButton(text='编辑')
        self.edit_btn.clicked.connect(self.on_edit_clicked)

        self.move_up_btn: PushButton = PushButton(text='上移')
        self.move_up_btn.clicked.connect(self.on_move_up_clicked)

        self.delete_btn: PushButton = PushButton(text='删除')
        self.delete_btn.clicked.connect(self.on_delete_clicked)

        MultiPushSettingCard.__init__(
            self,
            icon=FluentIcon.SETTING,
            title='游戏',
            content='脚本',
            parent=parent,
            btn_list=[
                self.edit_btn,
                self.move_up_btn,
                self.delete_btn,
            ]
        )
        self.config: ScriptConfig = config
        self.init_by_config(config)

    def on_edit_clicked(self) -> None:
        """
        点击编辑 弹出窗口
        :return:
        """
        dialog = ScriptEditDialog(config=self.edit_btn.property('config'),
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
        self.setTitle(f'游戏 {self.config.game_display_name}')
        self.setContent(f'脚本 {self.config.script_display_name}')

        self.edit_btn.setProperty('config', config)
        self.move_up_btn.setProperty('idx', config.idx)
        self.delete_btn.setProperty('idx', config.idx)

    def on_move_up_clicked(self) -> None:
        """
        上移
        """
        self.move_up.emit(self.move_up_btn.property('idx'))

    def on_delete_clicked(self) -> None:
        """
        删除
        """
        self.deleted.emit(self.delete_btn.property('idx'))


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
        self.chosen_config: Optional[ScriptChainConfig] = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.help_opt = HyperlinkCard(icon=FluentIcon.HELP, title='使用说明', text='前往',
                                      url='https://one-dragon.org/tools/zh/script_chainer.html')
        self.help_opt.setContent('先看说明 再使用与提问')
        content_widget.add_widget(self.help_opt)

        self.chain_combo_box = ComboBox()
        self.chain_combo_box.currentIndexChanged.connect(self.on_chain_selected)
        self.add_chain_btn: PushButton = PushButton(text='新增')
        self.add_chain_btn.clicked.connect(self.on_add_chain_clicked)
        self.chain_opt = MultiPushSettingCard(
            icon=FluentIcon.SETTING,
            title='脚本链',
            btn_list=[
                self.chain_combo_box,
                self.add_chain_btn
            ]
        )
        content_widget.add_widget(self.chain_opt)

        self.script_group = SettingCardGroup(gt('脚本链', 'ui'))
        self.script_card_list: list[ScriptSettingCard] = []
        content_widget.add_widget(self.script_group)

        self.add_script_btn = PrimaryPushButton(text='增加脚本')
        self.add_script_btn.clicked.connect(self.on_add_script_clicked)
        content_widget.add_widget(self.add_script_btn)

        content_widget.add_stretch(1)

        return content_widget

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.update_chain_combo_box()
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
        self.script_group.setVisible(chosen)
        self.add_script_btn.setVisible(chosen)

        if not chosen:
            return

        # 如果当前group中数量多 则删除
        while len(self.script_card_list) > len(self.chosen_config.script_list):
            last_card = self.script_card_list.pop()
            last_card.setParent(None)
            self.script_group.cardLayout.removeWidget(last_card)
            self.script_group.adjustSize()

        # 初始化已有的显示 group中数量不足则新增
        for i in range(len(self.chosen_config.script_list)):
            if i < len(self.script_card_list):
                card: ScriptSettingCard = self.script_card_list[i]
                card.init_by_config(self.chosen_config.script_list[i])
            else:
                card: ScriptSettingCard = ScriptSettingCard(self.chosen_config.script_list[i], parent=self.script_group)
                card.setVisible(True)
                self.script_card_list.append(card)
                self.script_group.addSettingCard(card)
                card.value_changed.connect(self.script_config_changed)
                card.move_up.connect(self.script_config_move_up)
                card.deleted.connect(self.script_config_deleted)

    def script_config_changed(self, config: ScriptConfig) -> None:
        """
        脚本配置变化
        """
        if self.chosen_config is None:
            return

        self.chosen_config.update_config(config)

    def script_config_move_up(self, idx: int) -> None:
        """
        脚本配置上移
        """
        if self.chosen_config is None:
            return

        self.chosen_config.move_up(idx)
        self.update_chain_display()

    def script_config_deleted(self, idx: int) -> None:
        """
        脚本配置删除
        """
        if self.chosen_config is None:
            return

        self.chosen_config.delete_one(idx)
        self.update_chain_display()
