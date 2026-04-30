from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    ColorDialog,
    FluentIcon,
    SettingCardGroup,
    Theme,
    setTheme,
)

from one_dragon.custom.custom_config import ThemeEnum
from one_dragon_qt.services.theme_manager import ThemeManager
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import (
    ComboBoxSettingCard,
)
from one_dragon_qt.widgets.setting_card.push_setting_card import PushSettingCard
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from script_chainer.context.script_chainer_context import ScriptChainerContext


class EditorSettingInterface(VerticalScrollInterface):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        self.ctx: ScriptChainerContext = ctx

        VerticalScrollInterface.__init__(
            self,
            nav_icon=FluentIcon.SETTING,
            object_name='editor_setting_interface',
            content_widget=None, parent=parent,
            nav_text_cn='设置'
        )

    def get_content_widget(self) -> QWidget:
        content_widget = Column()

        content_widget.add_widget(self.get_basic_group())

        content_widget.add_stretch(1)
        return content_widget

    def get_basic_group(self) -> SettingCardGroup:
        group = SettingCardGroup('基础')

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

    def on_interface_shown(self) -> None:
        VerticalScrollInterface.on_interface_shown(self)
        self.theme_opt.init_with_adapter(self.ctx.custom_config.get_prop_adapter('theme'))

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

