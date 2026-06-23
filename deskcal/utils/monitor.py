"""显示器组合签名：区分"笔记本单屏"和"接显示器后多屏"，用于分别记忆悬浮窗位置。"""
from __future__ import annotations

from PyQt6.QtGui import QGuiApplication


def compute_monitor_signature() -> str:
    """按当前所有显示器的分辨率+位置+缩放比拼成一个签名，组合不变签名就不变。"""
    parts = []
    for screen in QGuiApplication.screens():
        geometry = screen.geometry()
        parts.append(
            f"{geometry.width()}x{geometry.height()}@{geometry.x()},{geometry.y()}"
            f":{screen.devicePixelRatio():.2f}"
        )
    return "|".join(sorted(parts))
