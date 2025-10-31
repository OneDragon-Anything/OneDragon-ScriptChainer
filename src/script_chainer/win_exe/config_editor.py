from PySide6.QtWidgets import QApplication
from qfluentwidgets import NavigationItemPosition, setTheme, Theme

from one_dragon.version import __version__
from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.view.like_interface import LikeInterface
from one_dragon_qt.view.setting.setting_push_interface import SettingPushInterface
from one_dragon_qt.windows.app_window_base import AppWindowBase
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.gui.page.editor_setting_interface import EditorSettingInterface
from script_chainer.gui.page.script_setting_interface import ScriptSettingInterface


class AppWindow(AppWindowBase):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        """初始化主窗口类，设置窗口标题和图标"""
        self.ctx: ScriptChainerContext = ctx
        AppWindowBase.__init__(
            self,
            win_title="一条龙 千机链 配置器",
            project_config=ctx.project_config,
            app_icon="editor_icon.ico",
            parent=parent,
        )

    # 继承初始化函数
    def init_window(self):
        self.resize(960, 700)

        # 初始化位置
        self.move(100, 100)

        # 设置配置ID
        self.setObjectName("PhosWindow")
        self.navigationInterface.setObjectName("NavigationInterface")
        self.stackedWidget.setObjectName("StackedWidget")
        self.titleBar.setObjectName("TitleBar")

        # 布局样式调整
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.areaLayout.setContentsMargins(0, 32, 0, 0)
        self.navigationInterface.setContentsMargins(0, 0, 0, 0)

        # 配置样式
        OdQtStyleSheet.APP_WINDOW.apply(self)
        OdQtStyleSheet.NAVIGATION_INTERFACE.apply(self.navigationInterface)
        OdQtStyleSheet.STACKED_WIDGET.apply(self.stackedWidget)
        OdQtStyleSheet.AREA_WIDGET.apply(self.areaWidget)
        OdQtStyleSheet.TITLE_BAR.apply(self.titleBar)

        self.titleBar.setVersion(__version__)

    def create_sub_interface(self):
        """创建和添加各个子界面"""
        self.add_sub_interface(ScriptSettingInterface(self.ctx, parent=self))

        self.add_sub_interface(
            LikeInterface(self.ctx, parent=self),
            position=NavigationItemPosition.BOTTOM,
        )

        self.add_sub_interface(
            SettingPushInterface(self.ctx, parent=self),
            position=NavigationItemPosition.BOTTOM,
        )

        self.add_sub_interface(
            EditorSettingInterface(self.ctx, parent=self),
            position=NavigationItemPosition.BOTTOM,
        )


def __run():
    ctx = ScriptChainerContext()
    setTheme(Theme[ctx.custom_config.theme.upper()], lazy=True)
    app = QApplication([])
    window = AppWindow(ctx)
    window.show()
    window.activateWindow()
    app.exec()
    ctx.after_app_shutdown()


if __name__ == "__main__":
    __run()
