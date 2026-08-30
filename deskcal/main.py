"""程序入口：贴底层日历窗口 + 系统托盘，无控制台（打包时配合 --noconsole）。

首次运行（检测不到 onboarding_completed 标记）时先弹引导向导，填完/跳过后才进入正常流程。
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from deskcal.core.storage import TaskStore, load_appearance
from deskcal.services import autostart
from deskcal.services.lunar_holiday import ensure_default_holidays_seeded
from deskcal.services.schedule_reminder import ScheduleReminderService
from deskcal.services.single_instance import SingleInstance
from deskcal.tray.tray_icon import TrayIcon
from deskcal.ui.desktop_overlay.overlay_window import OverlayWindow
from deskcal.ui.desktop_overlay.widgets.registry import WidgetConfigStore
from deskcal.ui.onboarding.wizard import OnboardingWizard
from deskcal.utils import crypto
from deskcal.utils.icons import app_icon


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    open_settings_requested = "--background" not in sys.argv[1:]
    single_instance = SingleInstance()
    if not single_instance.become_primary():
        if open_settings_requested:
            single_instance.request_open_settings()
        return

    pending_open_settings = [open_settings_requested]
    single_instance.open_settings_requested.connect(
        lambda: pending_open_settings.__setitem__(0, True)
    )
    ensure_default_holidays_seeded()

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
    single_instance.open_settings_requested.connect(window.open_config_panel)
    if pending_open_settings[0]:
        QTimer.singleShot(0, window.open_config_panel)
    reminders = ScheduleReminderService(tray.show_course_reminder, parent=tray)
    reminders.start()
    QTimer.singleShot(700, window.maybe_start_guided_tour)

    if load_appearance()["autostart_enabled"]:
        autostart.enable_autostart()
    else:
        autostart.disable_autostart()

    exit_code = app.exec()
    single_instance.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
