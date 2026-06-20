"""系统托盘图标：打开设置面板（Phase 4 占位）/ 锁定桌面位置 / 临时隐藏15秒 / 退出。"""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from deskcal.ui.desktop_overlay.overlay_window import OverlayWindow

HIDE_DURATION_MS = 15_000


def _build_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setBrush(QColor("#e53935"))
    painter.setPen(QColor("#ffffff"))
    painter.drawEllipse(2, 2, 28, 28)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: OverlayWindow, parent=None):
        super().__init__(_build_tray_icon(), parent)
        self._window = window

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._window.show)

        menu = QMenu()

        self._config_action = menu.addAction("打开设置面板")
        self._config_action.triggered.connect(self._window.open_config_panel)

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
        self.setToolTip("DeskCal")

    def _hide_temporarily(self) -> None:
        self._window.hide()
        self._hide_timer.start(HIDE_DURATION_MS)
