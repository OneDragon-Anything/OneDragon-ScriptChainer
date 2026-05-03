from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition


def show_info(parent: QWidget, level: str, title: str, content: str, duration: int = 3000) -> None:
    """显示 InfoBar 通知。"""
    getattr(InfoBar, level)(
        title=title,
        content=content,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=duration,
        parent=parent,
    )


def show_success(parent: QWidget, title: str, content: str) -> None:
    show_info(parent, 'success', title, content)


def show_warning(parent: QWidget, title: str, content: str) -> None:
    show_info(parent, 'warning', title, content)


def show_error(parent: QWidget, title: str, content: str) -> None:
    show_info(parent, 'error', title, content, duration=5000)
