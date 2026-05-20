from collections.abc import Iterable
from enum import Enum

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    FluentIconBase,
    LineEdit,
    PushButton,
    ToolButton,
)

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.utils.i18_utils import gt
from one_dragon_qt.utils.layout_utils import IconSize, Margins
from one_dragon_qt.widgets.adapter_init_mixin import AdapterInitMixin
from one_dragon_qt.widgets.combo_box import ComboBox
from one_dragon_qt.widgets.setting_card.setting_card_base import SettingCardBase


class MultiValueDisplayComboBoxSettingCard(SettingCardBase, AdapterInitMixin):
    """多个单行输入配合预设下拉的设置卡片，适合列表值配置。"""

    value_changed = Signal(list)

    def __init__(self,
                 icon: str | QIcon | FluentIconBase, title: str, content: str | None = None,
                 icon_size: IconSize = IconSize(16, 16),
                 margins: Margins = Margins(16, 16, 0, 16),
                 options_enum: Iterable[Enum] | None = None,
                 options_list: list[ConfigItem] | None = None,
                 input_placeholder: str | None = None,
                 input_width: int = 360,
                 combo_width: int = 220,
                 add_button_text: str | None = None,
                 preset_placeholder: str | None = None,
                 parent: QWidget | None = None):

        SettingCardBase.__init__(
            self,
            icon=icon,
            title=title,
            content=content,
            icon_size=icon_size,
            margins=margins,
            parent=parent,
        )
        AdapterInitMixin.__init__(self)
        self.vBoxLayout.setSpacing(8)

        self._fixed_content = content or ''
        self._input_placeholder = input_placeholder or ''
        self._input_width = input_width
        self._opts_list: list[ConfigItem] = []
        self._error_message: str | None = None

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)
        self.hBoxLayout.addLayout(self.main_layout)

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(8)
        self.main_layout.addLayout(self.header_layout)

        self.combo_box = ComboBox(self)
        self.combo_box.setPlaceholderText(preset_placeholder or '自定义')
        self.combo_box.setMinimumWidth(combo_width)
        self.header_layout.addStretch(1)
        self.header_layout.addWidget(self.combo_box)
        self.header_layout.addSpacing(16)

        self.value_layout = QVBoxLayout()
        self.value_layout.setContentsMargins(0, 0, 0, 0)
        self.value_layout.setSpacing(8)
        self.main_layout.addLayout(self.value_layout)

        self.add_btn = PushButton(FluentIcon.ADD, gt(add_button_text or '新增'), self)
        self.add_btn.clicked.connect(lambda: self._add_row())

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addSpacing(16)
        self.main_layout.addLayout(btn_layout)

        self.error_label = CaptionLabel('', self)
        self.error_label.setTextColor('#cf1010', QColor(255, 28, 32))
        self.error_label.hide()
        self.main_layout.addWidget(self.error_label)

        self._initialize_options(options_enum, options_list)
        self.combo_box.currentIndexChanged.connect(self._on_preset_changed)

        self._add_row(emit_signal=False)
        self._update_height()

    def _initialize_options(
            self,
            options_enum: Iterable[Enum] | None,
            options_list: list[ConfigItem] | None,
    ) -> None:
        if options_list is not None:
            self.set_options_by_list(options_list)
        elif options_enum is not None:
            self.set_options_by_list([
                opt.value
                for opt in options_enum
                if isinstance(opt.value, ConfigItem)
            ])
        else:
            self.set_options_by_list([])

    def set_options_by_list(self, options: list[ConfigItem]) -> None:
        self._opts_list = list(options)
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        for opt in self._opts_list:
            self.combo_box.addItem(opt.ui_text, userData=opt.value)
        self.combo_box.blockSignals(False)
        self._sync_preset_selection(self.getValue())

    def _add_row(
        self,
        value: str = '',
        emit_signal: bool = True,
        refresh_layout: bool = True,
    ) -> None:
        row_widget = QWidget(self)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        input_container = QWidget(self)
        input_container.setProperty('_original_style_sheet', input_container.styleSheet())
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(1, 1, 1, 1)
        input_layout.setSpacing(0)

        value_edit = LineEdit(self)
        value_edit.setPlaceholderText(self._input_placeholder)
        value_edit.setMinimumWidth(self._input_width)
        value_edit.setText(value)
        value_edit.setProperty('_original_style_sheet', value_edit.styleSheet())
        value_edit.setProperty('_error_container', input_container)
        value_edit.editingFinished.connect(self._on_value_changed)
        input_layout.addWidget(value_edit)

        remove_btn = ToolButton(FluentIcon.DELETE, self)
        remove_btn.setFixedSize(30, 30)
        remove_btn.clicked.connect(lambda: self._remove_row(row_widget))

        row_layout.addWidget(input_container)
        row_layout.addWidget(remove_btn)
        row_layout.addSpacing(16)

        self.value_layout.addWidget(row_widget)
        self._apply_error_state_to_line_edit(value_edit)
        if refresh_layout:
            self._refresh_layout()

        if emit_signal and value:
            self._on_value_changed()

    def _remove_row(self, row_widget: QWidget) -> None:
        if self.value_layout.count() <= 1:
            return

        self.value_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._on_value_changed()
        self._refresh_layout()

    def _clear_rows(self) -> None:
        while self.value_layout.count():
            child = self.value_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_height(self) -> None:
        min_height = 110
        error_height = 24 if self.error_label.isVisible() else 0
        content_height = self.value_layout.count() * 40 + 110 + error_height
        self.setFixedHeight(max(min_height, content_height))

    def _update_all_remove_buttons(self) -> None:
        should_enable = self.value_layout.count() > 1
        for i in range(self.value_layout.count()):
            row_widget = self.value_layout.itemAt(i).widget()
            if row_widget:
                remove_btn = row_widget.findChild(ToolButton)
                if remove_btn:
                    remove_btn.setEnabled(should_enable)

    def _refresh_layout(self) -> None:
        self._update_height()
        self._update_all_remove_buttons()
        self.main_layout.activate()
        self.hBoxLayout.activate()
        self.updateGeometry()
        self.update()

    def _block_signals(self, value: bool) -> None:
        self.combo_box.blockSignals(value)
        for i in range(self.value_layout.count()):
            row_widget = self.value_layout.itemAt(i).widget()
            if row_widget:
                for line_edit in row_widget.findChildren(LineEdit):
                    line_edit.blockSignals(value)

    def _on_preset_changed(self, index: int) -> None:
        if index < 0:
            return
        values = self.combo_box.itemData(index)
        self.setValue(values)

    def _on_value_changed(self) -> None:
        values = self.getValue()
        self._sync_preset_selection(values)
        self.setContent(self._fixed_content)

        if self.adapter is not None:
            self.adapter.set_value(values)

        self.value_changed.emit(values)

    def _sync_preset_selection(self, values: list[str]) -> None:
        matched_index = -1
        for idx, opt in enumerate(self._opts_list):
            if list(opt.value) == values:
                matched_index = idx
                break

        self.combo_box.blockSignals(True)
        self.combo_box.setCurrentIndex(matched_index)
        self.combo_box.blockSignals(False)

    def getValue(self) -> list[str]:
        values: list[str] = []
        for i in range(self.value_layout.count()):
            row_widget = self.value_layout.itemAt(i).widget()
            if row_widget:
                line_edits = list(row_widget.findChildren(LineEdit))
                if line_edits:
                    value = line_edits[0].text().strip()
                    if value:
                        values.append(value)
        return values

    def setValue(self, value: list[str] | None, emit_signal: bool = True):
        values = list(value or [])
        if not emit_signal:
            self._block_signals(True)

        self.setUpdatesEnabled(False)
        try:
            self._clear_rows()
            if values:
                for item in values:
                    self._add_row(str(item), emit_signal=False, refresh_layout=False)
            else:
                self._add_row(emit_signal=False, refresh_layout=False)

            self._sync_preset_selection(self.getValue())
            self._refresh_layout()
            self.setContent(self._fixed_content)
        finally:
            self.setUpdatesEnabled(True)

        if emit_signal:
            self._on_value_changed()
        else:
            self._block_signals(False)

    def set_error_message(self, message: str | None) -> None:
        if self._error_message == message:
            return
        self._error_message = message
        self.error_label.setText(message or '')
        self.error_label.setVisible(bool(message))
        for i in range(self.value_layout.count()):
            row_widget = self.value_layout.itemAt(i).widget()
            if row_widget:
                line_edits = list(row_widget.findChildren(LineEdit))
                if line_edits:
                    self._apply_error_state_to_line_edit(line_edits[0])
        self._refresh_layout()

    def _apply_error_state_to_line_edit(self, line_edit: LineEdit) -> None:
        original_style = line_edit.property('_original_style_sheet')
        if original_style is None:
            original_style = line_edit.styleSheet()
            line_edit.setProperty('_original_style_sheet', original_style)
        error_container = line_edit.property('_error_container')
        if error_container is None:
            error_container = line_edit.parentWidget()

        if self._error_message:
            line_edit.setError(True)
            line_edit.setStyleSheet(str(original_style or ''))
            if isinstance(error_container, QWidget):
                error_container.setStyleSheet(
                    'QWidget { border: 1px solid #cf1010; border-radius: 6px; }'
                )
            line_edit.setToolTip(self._error_message)
        else:
            line_edit.setError(False)
            line_edit.setStyleSheet(str(original_style or ''))
            if isinstance(error_container, QWidget):
                original_container_style = error_container.property('_original_style_sheet')
                error_container.setStyleSheet(str(original_container_style or ''))
            line_edit.setToolTip('')
