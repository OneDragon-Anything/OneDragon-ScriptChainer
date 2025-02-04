from enum import Enum
from typing import Optional, List, Iterable, Any
from typing import Union

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtGui import Qt
from qfluentwidgets import FluentIconBase, LineEdit

from one_dragon.base.config.config_item import ConfigItem
from one_dragon_qt.utils.layout_utils import Margins, IconSize
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase
from one_dragon_qt.widgets.setting_card.yaml_config_adapter import YamlConfigAdapter


class ComboBoxSettingCard(SettingCardBase):
    """包含下拉框的自定义设置卡片类。"""

    value_changed = Signal(int, object)

    def __init__(self,
                 icon: Union[str, QIcon, FluentIconBase], title: str, content: Optional[str]=None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 options_enum: Optional[Iterable[Enum]] = None,
                 options_list: Optional[List[ConfigItem]] = None,
                 adapter: Optional[YamlConfigAdapter] = None,
                 with_custom_input: bool = False,
                 custom_opt_txt: str = '自定义',
                 custom_input_getter: str = 'str',
                 parent=None
                 ):
        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent
        )
        self.with_custom_input: bool = with_custom_input  # 是否允许输入自定义值
        self.custom_opt_txt: str = custom_opt_txt  # 自定义输入的选项文本
        self.custom_input_getter: str = custom_input_getter  # 自定义输入的值类型

        # 初始化下拉框
        self.combo_box = ComboBox(self)
        self.hBoxLayout.addWidget(self.combo_box, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        # 自定义输入框
        self.custom_input = LineEdit(self)
        self.custom_input.setContentsMargins(0, 0, 16, 0)
        self.custom_input.editingFinished.connect(self.on_custom_input_changed)
        self.hBoxLayout.addWidget(self.custom_input, 0, Qt.AlignmentFlag.AlignRight)

        self.adapter: YamlConfigAdapter = adapter

        # 初始化选项
        self._opts_list: List[ConfigItem] = []
        self._initialize_options(options_enum, options_list)

        # 设置初始索引
        self.last_index = -1
        if self.combo_box.count() > 0:
            self.combo_box.setCurrentIndex(0)
            self.last_index = 0
            self.custom_input.setVisible(self.is_current_custom_chosen)

        # 连接信号与槽
        self.combo_box.currentIndexChanged.connect(self._on_index_changed)

    def _initialize_options(self, options_enum: Optional[Iterable[Enum]], options_list: Optional[List[ConfigItem]]) -> None:
        """从枚举或列表初始化下拉框选项。"""
        if options_enum:
            for opt in options_enum:
                if isinstance(opt.value, ConfigItem):
                    self._opts_list.append(opt.value)
                    self.combo_box.addItem(opt.value.ui_text, userData=opt.value.value)
        elif options_list:
            for opt_item in options_list:
                self._opts_list.append(opt_item)
                self.combo_box.addItem(opt_item.ui_text, userData=opt_item.value)

        if self.with_custom_input:
            self.combo_box.addItem(self.custom_opt_txt, userData=None)

    def set_options_by_list(self, options: List[ConfigItem]) -> None:
        """通过 ConfigItem 列表设置下拉框选项。"""
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        self._opts_list.clear()

        for opt_item in options:
            self._opts_list.append(opt_item)
            self.combo_box.addItem(opt_item.ui_text, userData=opt_item.value)

        self.combo_box.blockSignals(False)

    def init_with_adapter(self, adapter: Optional[YamlConfigAdapter]) -> None:
        """初始化配置适配器。"""
        self.adapter = adapter
        self.setValue(None if adapter is None else adapter.get_value(), emit_signal=False)

    def _on_index_changed(self, index: int) -> None:
        """索引变化时发射信号。"""
        if index == self.last_index:
            return

        self.last_index = index
        self._update_desc()

        val = self.combo_box.currentData()
        if self.with_custom_input:
            if self.is_current_custom_chosen:
                val = self.get_custom_input_value()
                self.custom_input.setVisible(True)
            else:
                self.custom_input.setText(str(val))
                self.custom_input.setVisible(False)
        else:
            self.custom_input.setVisible(False)

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(index, val)

    def _update_desc(self) -> None:
        """更新描述显示。"""
        if self.combo_box.currentIndex() >= 0 and self.combo_box.currentIndex() < len(self._opts_list):
            desc = self._opts_list[self.combo_box.currentIndex()].desc
            self.setContent(desc)
        else:
            self.setContent('')

    def setValue(self, value: object, emit_signal: bool = True) -> None:
        """设置下拉框的值。"""
        if not emit_signal:
            self.combo_box.blockSignals(True)
            self.custom_input.blockSignals(True)

        if value is None:
            if self.with_custom_input:
                self.combo_box.setCurrentIndex(len(self.combo_box.items) - 1)
                self.custom_input.setText('')
            else:
                self.last_index = -1
                self.combo_box.setCurrentIndex(-1)
        else:
            self.last_index = -1
            for idx in range(self.combo_box.count()):
                if self.combo_box.itemData(idx) == value:
                    self.last_index = idx
                    self.combo_box.setCurrentIndex(idx)
                    break

            if self.last_index == -1 and self.with_custom_input:
                self.combo_box.setCurrentIndex(len(self.combo_box.items) - 1)
                self.custom_input.setText(str(value))

        if not emit_signal:
            self.combo_box.blockSignals(False)
            self.custom_input.blockSignals(False)

        self._update_desc()

    def getValue(self) -> Any:
        """获取当前选中的值。"""
        if self.with_custom_input:
            if self.is_current_custom_chosen:
                return self.get_custom_input_value()
            else:
                return self.combo_box.currentData()
        else:
            return self.combo_box.currentData()

    @property
    def is_current_custom_chosen(self) -> bool:
        text = self.combo_box.currentText()
        val = self.combo_box.currentData()
        return self.with_custom_input and val is None and text == self.custom_opt_txt

    def get_custom_input_value(self) -> Any:
        """
        获取自定义输入的值
        """
        val = self.custom_input.text()
        if self.custom_input_getter == 'int':
            val = int(val)
        return val

    def on_custom_input_changed(self) -> None:
        """
        自定义值的更改
        """
        val = self.get_custom_input_value()

        if self.adapter is not None:
            self.adapter.set_value(val)

        self.value_changed.emit(self.combo_box.currentIndex(), val)
