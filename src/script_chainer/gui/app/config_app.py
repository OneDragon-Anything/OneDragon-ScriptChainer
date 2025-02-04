from PySide6.QtWidgets import QApplication

from one_dragon_qt.services.styles_manager import OdQtStyleSheet
from one_dragon_qt.windows.app_window_base import AppWindowBase
from script_chainer.context.script_chainer_context import ScriptChainerContext
from script_chainer.gui.page.script_setting_interface import ScriptSettingInterface


class AppWindow(AppWindowBase):

    def __init__(self, ctx: ScriptChainerContext, parent=None):
        """初始化主窗口类，设置窗口标题和图标"""
        self.ctx: ScriptChainerContext = ctx
        AppWindowBase.__init__(
            self,
            win_title="一条龙 千机链",
            project_config=ctx.project_config,
            app_icon="zzz_logo.ico",
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

    def create_sub_interface(self):
        """创建和添加各个子界面"""
        self.add_sub_interface(ScriptSettingInterface(self.ctx, parent=self))
        # 点赞
        # self.add_sub_interface(
        #     LikeInterface(self.ctx, parent=self),
        #     position=NavigationItemPosition.BOTTOM,
        # )


def __run():
    ctx = ScriptChainerContext()
    app = QApplication([])
    window = AppWindow(ctx)
    window.show()
    app.exec()
    ctx.after_app_shutdown()


if __name__ == "__main__":
    __run()
