"""应用图标：所有窗口/托盘图标统一从这里取，方便以后换图只改一处。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon

APP_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "images" / "logo.png"


def app_icon() -> QIcon:
    return QIcon(str(APP_ICON_PATH))
