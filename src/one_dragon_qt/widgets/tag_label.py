from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets.common.config import qconfig

from one_dragon_qt.utils.color_utils import get_foreground_color


class TagLabel(QLabel):
    """小型圆角标签组件。

    不指定 ``color`` 时背景跟随全局主题色自动更新；
    指定 ``color`` 后使用固定颜色，不跟随主题变化。
    """

    def __init__(
        self,
        text: str,
        color: QColor | str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(text, parent)
        self.setFixedHeight(18)

        if color is not None:
            fixed_color = QColor(color)
            if not fixed_color.isValid():
                raise ValueError(f"无效的标签颜色: {color!r}")
            self._apply_fixed(fixed_color)
        else:
            qconfig.themeColorChanged.connect(self._apply_theme)
            self._apply_theme(qconfig.get(qconfig.themeColor))

    def _apply_fixed(self, color: QColor) -> None:
        r, g, b = color.red(), color.green(), color.blue()
        fg = get_foreground_color(r, g, b)
        self.setStyleSheet(
            f'background-color: {color.name()};'
            f'color: {fg};'
            f'border-radius: 4px;'
            f'padding: 1px 6px;'
            f'font-size: 11px;'
        )

    def _apply_theme(self, color: QColor) -> None:
        self._apply_fixed(color)
