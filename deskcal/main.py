"""程序入口：贴底层日历窗口 + 系统托盘，无控制台（打包时配合 --noconsole）。

首次运行（检测不到 onboarding_completed 标记）时先弹引导向导，填完/跳过后才进入正常流程。
"""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from deskcal.core.storage import TaskStore
from deskcal.services import autostart
from deskcal.tray.tray_icon import TrayIcon
from deskcal.ui.desktop_overlay.overlay_window import OverlayWindow
from deskcal.ui.desktop_overlay.widgets.registry import WidgetConfigStore
from deskcal.ui.onboarding.wizard import OnboardingWizard
from deskcal.utils import crypto


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not crypto.is_onboarding_completed():
        widget_store = WidgetConfigStore()
        widget_store.load()
        wizard = OnboardingWizard(widget_store)
        wizard.exec()

    store = TaskStore()
    store.load()

    window = OverlayWindow(store)
    window.show()
    app.aboutToQuit.connect(window.persist_geometry)

    tray = TrayIcon(window)
    tray.show()

    autostart.enable_autostart()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
