"""显示器组合签名：区分"笔记本单屏"和"接显示器后多屏"，用于分别记忆悬浮窗位置。"""
from __future__ import annotations

from PyQt6.QtGui import QGuiApplication


def compute_screen_signature(screen) -> str:
    """返回单块显示器的稳定配置标识，用于保存该屏幕独有的界面偏好。"""
    geometry = screen.geometry()
    return (
        f"{screen.name()}:{geometry.width()}x{geometry.height()}"
        f":{screen.devicePixelRatio():.2f}"
    )


def describe_screen(screen) -> str:
    """返回设置界面使用的可读显示器说明。"""
    geometry = screen.geometry()
    return (
        f"{screen.name()} · {geometry.width()}×{geometry.height()}"
        f" · {screen.devicePixelRatio():.2f}× 缩放"
    )


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
