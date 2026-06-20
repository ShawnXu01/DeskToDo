"""时钟组件：单例型，撑满组件区宽度，数码管（七段管）风格显示，每秒刷新。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

ROW_HEIGHT = 70

_DSEG_FONT_PATH = Path(__file__).resolve().parents[3] / "assets" / "fonts" / "DSEG7Classic-Bold.ttf"
_dseg_family: str | None = None


def _load_dseg_family() -> str | None:
    """把内置的 DSEG7-Classic 数码管字体注册进 Qt 字体库，找不到就退回系统等宽字体。"""
    global _dseg_family
    if _dseg_family is not None:
        return _dseg_family
    font_id = QFontDatabase.addApplicationFont(str(_DSEG_FONT_PATH))
    families = QFontDatabase.applicationFontFamilies(font_id)
    _dseg_family = families[0] if families else ""
    return _dseg_family or None


def default_clock_config() -> dict:
    return {}


class ClockWidget(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setFixedHeight(ROW_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._time_label = QLabel()
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        family = _load_dseg_family()
        font = QFont(family if family else "Consolas")
        font.setPointSize(28)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 105)
        self._time_label.setFont(font)
        self._time_label.setStyleSheet("color: #ffffff; background: transparent;")

        layout.addWidget(self._time_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self) -> None:
        self._time_label.setText(datetime.now().strftime("%H:%M:%S"))
