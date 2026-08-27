"""macOS 桌面窗口原型：验证窗口层级、Spaces、显示桌面和多显示器行为。

本文件是独立探针，不参与 DeskToDo 正式程序启动。只有实机验证通过后，
其中的原生窗口策略才会迁入平台适配层。
"""
from __future__ import annotations

import ctypes
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPoint, QRectF, QT_VERSION_STR, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QGuiApplication, QIcon, QMouseEvent, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import PYQT_VERSION_STR


if sys.platform != "darwin":
    raise SystemExit("该探针只能在 macOS 上运行。")

import objc  # noqa: E402  # 仅 macOS 可用
from AppKit import (  # noqa: E402
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenNone,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
)
from Quartz import (  # noqa: E402
    CGWindowLevelForKey,
    kCGDesktopIconWindowLevelKey,
    kCGDesktopWindowLevelKey,
    kCGNormalWindowLevelKey,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT_DIR / "deskcal" / "assets" / "images" / "logo.png"


@dataclass(frozen=True)
class WindowLevelChoice:
    key: str
    label: str
    level: int


def native_window_for(widget: QWidget):
    """把 Qt 在 macOS 上返回的 NSView* 转为 PyObjC 对象，并取得 NSWindow。"""
    view_pointer = ctypes.c_void_p(int(widget.winId()))
    native_view = objc.objc_object(c_void_p=view_pointer)
    native_window = native_view.window()
    if native_window is None:
        raise RuntimeError("Qt 原生 NSView 尚未连接到 NSWindow")
    return native_window


def available_window_levels() -> list[WindowLevelChoice]:
    desktop_level = int(CGWindowLevelForKey(kCGDesktopWindowLevelKey))
    desktop_icon_level = int(CGWindowLevelForKey(kCGDesktopIconWindowLevelKey))
    normal_level = int(CGWindowLevelForKey(kCGNormalWindowLevelKey))
    return [
        WindowLevelChoice(
            "below_desktop_icons",
            "桌面图标下方一级（推荐）",
            desktop_icon_level - 1,
        ),
        WindowLevelChoice(
            "above_desktop",
            "桌面层上方一级（备用）",
            desktop_level + 1,
        ),
        WindowLevelChoice(
            "below_normal_windows",
            "普通窗口下方一级（诊断）",
            normal_level - 1,
        ),
    ]


def collection_behavior(show_on_all_spaces: bool) -> int:
    behavior = (
        int(NSWindowCollectionBehaviorStationary)
        | int(NSWindowCollectionBehaviorIgnoresCycle)
        | int(NSWindowCollectionBehaviorFullScreenNone)
    )
    if show_on_all_spaces:
        behavior |= int(NSWindowCollectionBehaviorCanJoinAllSpaces)
    return behavior


class ProbeWindow(QWidget):
    diagnostic_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DeskToDo macOS 桌面窗口探针")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(700, 430)

        self._native_window = None
        self._drag_offset: Optional[QPoint] = None
        self._levels = available_window_levels()
        self._last_error = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        title = QLabel("DeskToDo · macOS 桌面窗口探针")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        outer.addWidget(title)

        description = QLabel(
            "请用这个窗口验证：普通窗口覆盖、显示桌面保留、全屏应用隐藏、"
            "Spaces 开关和多显示器拖动。此程序不会读写 DeskToDo 用户数据。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 14px; color: rgba(255,255,255,210);")
        outer.addWidget(description)

        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("原生窗口层级"))
        self._level_combo = QComboBox()
        for choice in self._levels:
            self._level_combo.addItem(f"{choice.label} · level={choice.level}", choice.key)
        self._level_combo.currentIndexChanged.connect(self.apply_native_behavior)
        level_row.addWidget(self._level_combo, 1)
        outer.addLayout(level_row)

        option_row = QHBoxLayout()
        self._all_spaces = QCheckBox("在所有桌面空间显示（不包含全屏应用）")
        self._all_spaces.setChecked(True)
        self._all_spaces.toggled.connect(self.apply_native_behavior)
        option_row.addWidget(self._all_spaces)

        self._locked = QCheckBox("锁定位置")
        self._locked.setChecked(False)
        option_row.addWidget(self._locked)
        option_row.addStretch(1)
        outer.addLayout(option_row)

        button_row = QHBoxLayout()
        apply_button = QPushButton("重新应用原生行为")
        apply_button.clicked.connect(self.apply_native_behavior)
        button_row.addWidget(apply_button)

        copy_button = QPushButton("复制诊断信息")
        copy_button.clicked.connect(self.copy_diagnostics)
        button_row.addWidget(copy_button)

        hide_button = QPushButton("隐藏 5 秒")
        hide_button.clicked.connect(self.hide_temporarily)
        button_row.addWidget(hide_button)
        button_row.addStretch(1)
        outer.addLayout(button_row)

        self._status = QLabel("等待连接 AppKit NSWindow…")
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._status.setStyleSheet(
            "background: rgba(0,0,0,80); border-radius: 8px; padding: 10px; "
            "font-family: Menlo; font-size: 11px; color: rgba(255,255,255,220);"
        )
        outer.addWidget(self._status, 1)

        hint = QLabel("未锁定时可拖动面板空白区域；如果窗口找不到，请使用菜单栏图标恢复。")
        hint.setStyleSheet("font-size: 12px; color: rgba(255,255,255,150);")
        outer.addWidget(hint)

        self.setStyleSheet(
            "QWidget { color: white; }"
            "QComboBox, QPushButton { color: #111; padding: 5px 8px; }"
            "QCheckBox { spacing: 7px; }"
        )

        QTimer.singleShot(0, self.apply_native_behavior)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)
        painter.fillPath(path, QColor(18, 22, 30, 225))
        painter.end()
        super().paintEvent(event)

    def selected_level(self) -> WindowLevelChoice:
        key = self._level_combo.currentData()
        return next(choice for choice in self._levels if choice.key == key)

    def apply_native_behavior(self, *_args) -> None:
        try:
            native_window = native_window_for(self)
            choice = self.selected_level()
            behavior = collection_behavior(self._all_spaces.isChecked())

            native_window.setLevel_(choice.level)
            native_window.setCollectionBehavior_(behavior)
            native_window.setHidesOnDeactivate_(False)
            native_window.setCanHide_(False)
            native_window.setExcludedFromWindowsMenu_(True)
            native_window.setHasShadow_(False)

            self._native_window = native_window
            self._last_error = ""
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
        self.refresh_diagnostics()

    def diagnostic_payload(self) -> dict:
        geometry = self.geometry()
        screens = []
        for screen in QGuiApplication.screens():
            rect = screen.geometry()
            screens.append(
                {
                    "name": screen.name(),
                    "geometry": [rect.x(), rect.y(), rect.width(), rect.height()],
                    "device_pixel_ratio": screen.devicePixelRatio(),
                }
            )
        choice = self.selected_level()
        return {
            "probe": "DeskToDo macOS desktop window probe",
            "platform": platform.platform(),
            "machine": platform.machine(),
            "mac_version": platform.mac_ver()[0],
            "python": platform.python_version(),
            "pyqt": PYQT_VERSION_STR,
            "qt": QT_VERSION_STR,
            "level_key": choice.key,
            "level": choice.level,
            "all_spaces": self._all_spaces.isChecked(),
            "locked": self._locked.isChecked(),
            "collection_behavior": collection_behavior(self._all_spaces.isChecked()),
            "window_geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
            "screens": screens,
            "native_window_connected": self._native_window is not None,
            "error": self._last_error or None,
        }

    def refresh_diagnostics(self) -> None:
        payload = self.diagnostic_payload()
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        self._status.setText(text)
        self.diagnostic_changed.emit(text)
        print(text, flush=True)

    def copy_diagnostics(self) -> None:
        text = json.dumps(self.diagnostic_payload(), ensure_ascii=False, indent=2)
        QApplication.clipboard().setText(text)
        self._status.setText(text + "\n\n诊断信息已复制到剪贴板。")

    def hide_temporarily(self) -> None:
        self.hide()
        QTimer.singleShot(5000, self.restore_from_menu)

    def restore_from_menu(self) -> None:
        self.show()
        QTimer.singleShot(0, self.apply_native_behavior)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self._locked.isChecked():
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class ProbeTray(QSystemTrayIcon):
    def __init__(self, window: ProbeWindow) -> None:
        icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )
        super().__init__(icon, window)
        self.setToolTip("DeskToDo macOS 桌面窗口探针")

        menu = QMenu()
        show_action = QAction("显示并重新应用窗口行为", self)
        show_action.triggered.connect(window.restore_from_menu)
        menu.addAction(show_action)

        menu.addSeparator()
        quit_action = QAction("退出探针", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        self.setContextMenu(menu)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DeskToDo macOS Desktop Probe")
    app.setQuitOnLastWindowClosed(False)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = ProbeWindow()
    tray = ProbeTray(window)
    tray.show()
    window.show()
    QTimer.singleShot(0, window.apply_native_behavior)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
