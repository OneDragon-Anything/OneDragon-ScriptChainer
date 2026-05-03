from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from qfluentwidgets import CaptionLabel, LineEdit, MessageBoxBase, SubtitleLabel


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
