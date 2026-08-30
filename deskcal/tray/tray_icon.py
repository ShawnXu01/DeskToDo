"""系统托盘图标：打开设置面板（Phase 4 占位）/ 锁定桌面位置 / 临时隐藏15秒 / 退出。"""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from deskcal.ui.desktop_overlay.overlay_window import OverlayWindow
from deskcal.utils.icons import app_icon

HIDE_DURATION_MS = 15_000


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: OverlayWindow, parent=None):
        super().__init__(app_icon(), parent)
        self._window = window

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._window.show)

        menu = QMenu()

        self._config_action = menu.addAction("打开设置面板")
        self._config_action.triggered.connect(self._window.open_config_panel)

        self._tour_action = menu.addAction("重新查看使用引导")
        self._tour_action.triggered.connect(self._window.start_guided_tour)
        self._window.set_tour_tray_hint_callback(self._show_tour_tray_hint)

        self._lock_action = menu.addAction("锁定桌面位置")
        self._lock_action.setCheckable(True)
        self._lock_action.setChecked(True)
        self._lock_action.toggled.connect(self._window.set_locked)

        self._hide_action = menu.addAction("临时隐藏15秒")
        self._hide_action.triggered.connect(self._hide_temporarily)

        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)
        self.setToolTip("DeskToDo")
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._window.open_config_panel()

    def _hide_temporarily(self) -> None:
        self._window.hide()
        self._hide_timer.start(HIDE_DURATION_MS)

    def _show_tour_tray_hint(self) -> None:
        self.showMessage(
            "DeskToDo 在这里",
            "左键托盘图标可以打开设置；右键可以解锁布局、临时隐藏或退出。",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def show_course_reminder(self, title: str, message: str) -> None:
        self.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            10_000,
        )
