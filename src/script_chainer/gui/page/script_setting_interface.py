import os
from typing import Optional

from PySide6.QtWidgets import QDialog, QFileDialog
from PySide6.QtWidgets import QWidget
from qfluentwidgets import SettingCardGroup, FluentIcon, PushButton, PrimaryPushButton, MessageBoxBase

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.multi_push_setting_card import MultiPushSettingCard
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.config.script_config import ScriptChainConfig, ScriptConfig
from script_chainer.context.script_chainer_context import ScriptChainerContext


class ScriptEditDialog(MessageBoxBase):
    def __init__(self, config: ScriptConfig, parent=None):
        MessageBoxBase.__init__(self, parent)
        self.yesButton.setText('保存')
        self.cancelButton.setText('取消')
        self.setMinimumWidth(800)

        self.config: ScriptConfig = config

        # 将组件添加到布局中
        self.script_path_opt = PushSettingCard(icon=FluentIcon.FOLDER, title='脚本路径', text='选择')
        self.script_path_opt.clicked.connect(self.on_script_path_clicked)
        self.viewLayout.addWidget(self.script_path_opt)

    def init_by_config(self, config: ScriptConfig):
        # 复制一个 防止修改了原来的
        self.config = ScriptConfig(
            script_path=config.script_path,
            script_window_title=config.script_window_title,
            game_window_title=config.game_window_title,
            run_timeout_seconds=config.run_timeout_seconds,
            check_done=config.check_done,
            script_arguments=config.script_arguments,
        )
        self.config.idx = config.idx

        self.script_path_opt.setContent(config.script_path)

    def on_script_path_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, gt('选择你的脚本'))
        if file_path is not None:
            self.on_script_path_chosen(os.path.normpath(file_path))

    def on_script_path_chosen(self, file_path) -> None:
        self.config.script_path = file_path
        self.script_path_opt.setContent(file_path)


class ScriptSettingCard(MultiPushSettingCard):

    def __init__(self, config: ScriptConfig, parent=None):
        self.edit_btn: PushButton = PushButton(text='编辑')
        self.edit_btn.clicked.connect(self.on_edit_clicked)

        MultiPushSettingCard.__init__(
            self,
            icon=FluentIcon.SETTING,
            title='游戏',
            content='脚本',
            parent=parent,
            btn_list=[
                self.edit_btn
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
        if dialog.exec():
            print("保存操作")
        else:
            print("取消操作")

    def init_by_config(self, config: ScriptConfig) -> None:
        """
        根据配置初始化
        :param config:
        :return:
        """
        self.config = config
        self.edit_btn.setProperty('config', config)
        self.setTitle(f'游戏 {self.config.game_window_title}')
        self.setContent(f'脚本 {self.config.script_display_name}')


class ScriptSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx: ScriptChainerContext = ctx

        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='script_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='脚本设置'
        )
        self.ctx: ScriptChainerContext = ctx
        self.chosen_config: Optional[ScriptChainConfig] = None

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

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
        while self.script_group.cardLayout.count() > len(self.chosen_config.script_list):
            self.script_group.cardLayout.removeWidget(self.script_group.cardLayout.widget(0))

        # 初始化已有的显示 group中数量不足则新增
        for i in range(len(self.chosen_config.script_list)):
            if i < self.script_group.cardLayout.count():
                card: ScriptSettingCard = self.script_group.cardLayout.itemAt(i).widget()
                card.config = self.chosen_config.script_list[i]
            else:
                card: ScriptSettingCard = ScriptSettingCard(self.chosen_config.script_list[i], parent=self.script_group)
                card.setVisible(True)
                self.script_group.addSettingCard(card)
