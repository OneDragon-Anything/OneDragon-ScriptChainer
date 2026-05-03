from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    Dialog,
    FluentIcon,
    PrimaryDropDownPushButton,
    PushButton,
    RoundMenu,
    SubtitleLabel,
    TransparentToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.widgets.base_interface import BaseInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.draggable_list import DraggableList, DraggableListItem
from one_dragon_qt.widgets.page_stack_wrapper import PageStackWrapper
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.config.script_config import (
    AttachDirection,
    ScriptChainConfig,
    ScriptConfig,
    ScriptType,
)
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.gui.page.script_edit_interface import ScriptEditInterface
from script_chainer.gui.page.script_setting_cards import (
    PythonScriptSettingCard,
    ScriptSettingCard,
)
from script_chainer.gui.page.script_setting_dialogs import ChainRenameDialog
from script_chainer.gui.page.script_setting_utils import (
    show_error,
    show_success,
    show_warning,
)
from script_chainer.utils.process_utils import launch_in_terminal
from script_chainer.utils.runner_utils import (
    build_runner_command,
)


class ScriptSettingRootInterface(VerticalScrollInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx: ScriptChainerContext = ctx

        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='script_setting_root_interface',
            content_widget=None, parent=parent,
            nav_text_cn='脚本链'
        )
        self.ctx: ScriptChainerContext = ctx
        self.chosen_config: ScriptChainConfig | None = None
        self._runner_launch_in_progress: bool = False

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        self.script_list_widget = DraggableList()
        self.script_list_widget.order_changed.connect(self.on_order_changed)
        self.script_card_list: list[DraggableListItem] = []
        content_widget.add_widget(self.script_list_widget)

        return content_widget

    def get_fixed_top_widget(self) -> QWidget | None:
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
        toolbar_layout.setContentsMargins(8, 8, 16, 8)
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

        return self.chain_toolbar

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)

        self.update_chain_combo_box()
        if self.chosen_config is None and self.chain_combo_box.count() > 0:
            self.chain_combo_box.setCurrentIndex(0)
        else:
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
            show_success(self.window(), '运行全部', f'已在终端启动脚本链 {chain_name}')
        except Exception as e:
            show_error(self.window(), '启动失败', str(e))
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
                card.edit_requested.connect(self.on_script_edit_requested)
            self.script_card_list.append(card)
            self.script_list_widget.add_list_item(card)

            card.value_changed.connect(self.script_config_changed)
            card.deleted.connect(self.script_config_deleted)

        self._update_attach_margins()

    def on_script_edit_requested(self, card: ScriptSettingCard) -> None:
        """推入外部程序脚本编辑二级界面。"""
        edit_interface = ScriptEditInterface(card.config, parent=self)
        edit_interface.saved.connect(
            lambda config, target_card=card: self._on_script_edit_saved(target_card, config)
        )
        edit_interface.canceled.connect(self._pop_secondary_interface)
        self._push_secondary_interface('编辑脚本', edit_interface)

    def _on_script_edit_saved(self, card: ScriptSettingCard, config: ScriptConfig) -> None:
        card.init_by_config(config)
        card.value_changed.emit(config)
        self._pop_secondary_interface()

    def _push_secondary_interface(self, title: str, content: QWidget) -> None:
        current = self.parent()
        while current is not None:
            push_setting_interface = getattr(current, 'push_setting_interface', None)
            if callable(push_setting_interface):
                push_setting_interface(title, content)
                return
            current = current.parent()
        show_warning(self.window(), '无法打开', '当前页面不支持二级设置界面')

    def _pop_secondary_interface(self) -> None:
        current = self.parent()
        while current is not None:
            pop_setting_interface = getattr(current, 'pop_setting_interface', None)
            if callable(pop_setting_interface):
                pop_setting_interface()
                return
            current = current.parent()

    def on_order_changed(self, new_data_list: list) -> None:
        """拖拽排序后的回调。

        Args:
            new_data_list: 新顺序的数据列表。
        """
        if self.chosen_config is None:
            return

        old_target_of = {
            id(config): target
            for config, target in zip(
                self.chosen_config.script_list,
                self.chosen_config.compute_attach_targets(),
                strict=False,
            )
        }

        # 更新卡片列表的顺序和索引
        new_card_list: list[DraggableListItem] = []
        for data in new_data_list:
            for card in self.script_card_list:
                if card.data is data:
                    new_card_list.append(card)
                    break
        self.script_card_list = new_card_list

        self.chosen_config.reorder(new_data_list)
        new_target_of = {
            id(config): target
            for config, target in zip(
                self.chosen_config.script_list,
                self.chosen_config.compute_attach_targets(),
                strict=False,
            )
        }

        for idx, card in enumerate(self.script_card_list):
            config = card.data
            if isinstance(config, ScriptConfig) and config.script_type == ScriptType.PYTHON:
                old_target = old_target_of.get(id(config))
                new_target = new_target_of.get(id(config))
                if old_target is not new_target:
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


class ScriptSettingInterface(BaseInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        BaseInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='script_setting_interface',
            nav_text_cn='脚本链',
            parent=parent,
        )
        self.root_interface = ScriptSettingRootInterface(ctx, parent=self)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.page_stack_wrapper = PageStackWrapper(self.root_interface, self)
        layout.addWidget(self.page_stack_wrapper)

    @property
    def is_secondary_shown(self) -> bool:
        return self.page_stack_wrapper.is_secondary_shown

    def push_setting_interface(self, title: str, content: QWidget) -> None:
        self.page_stack_wrapper.push_setting(title, content)

    def pop_setting_interface(self) -> None:
        self.page_stack_wrapper.reset_to_root()

    def on_interface_shown(self) -> None:
        self.page_stack_wrapper.on_interface_shown()

    def on_interface_hidden(self) -> None:
        self.page_stack_wrapper.on_interface_hidden()
