"""跨模块共用的小型样式工具：
- 滚动区域透明化（QAbstractScrollArea 的 viewport 默认会用调色板填充不透明背景，
  必须连 viewport 一起处理才能真的透出去）。
- ElidingLabel：容器宽度可变（侧栏/组件区现在可以被用户拖拽调整）时，文字太长就用
  "..." 省略号裁切，而不是被硬裁切到看不见。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QScrollArea


def make_scroll_area_transparent(scroll_area: QScrollArea) -> None:
    scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    scroll_area.viewport().setStyleSheet("background: transparent;")


class ElidingLabel(QLabel):
    """跟普通 QLabel 用法一样，但容器变窄时文字会自动省略号裁切而不是被硬裁切。"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text
        self._apply_elide()

    def setText(self, text: str) -> None:  # noqa: N802 (保持跟 QLabel 同名覆盖)
        self._full_text = text
        self._apply_elide()

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        elided = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided)
