"""任务条小组件：日历格子与待办收纳侧栏共用。

只负责展示和交互（勾选完成/双击或右键编辑），不直接持有任务对象，
由调用方通过信号回调去操作 store，保持组件本身与具体任务类型（DatedTask/FloatingTask）解耦。
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from deskcal.ui.style_utils import ElidingLabel


class TaskChipWidget(QWidget):
    editRequested = pyqtSignal()
    toggleCompleteRequested = pyqtSignal(bool)

    def __init__(self, *, name: str, color: str, completed: bool, parent=None):
        super().__init__(parent)
        self._completed = completed

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)

        self._checkbox = QCheckBox()
        self._checkbox.setChecked(completed)
        self._checkbox.toggled.connect(self.toggleCompleteRequested.emit)
        layout.addWidget(self._checkbox)

        self._color_dot = QLabel()
        self._color_dot.setFixedSize(8, 8)
        self._color_dot.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(self._color_dot)

        self._name_label = ElidingLabel(name)
        layout.addWidget(self._name_label, 1)

        self._apply_text_style()

    def _apply_text_style(self) -> None:
        color = "#aaaaaa" if self._completed else "#ffffff"
        self._name_label.setStyleSheet(f"color: {color};")

    def mouseDoubleClickEvent(self, event) -> None:
        self.editRequested.emit()
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self.editRequested.emit()
        event.accept()
