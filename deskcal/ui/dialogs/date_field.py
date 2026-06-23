"""单日期选择条：替代 QDateEdit，去掉下拉小三角和键盘输入，整条可点击弹出暗色日历。"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel

from deskcal.ui.dialogs.mini_calendar_picker import MiniCalendarPicker


class DateField(QFrame):
    dateChanged = pyqtSignal(date)

    def __init__(self, initial_date: date | None = None, parent=None):
        super().__init__(parent)
        self._date = initial_date or date.today()

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame { background-color: #2c2c2c; border: 1px solid #444444; border-radius: 4px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self._label = QLabel()
        self._label.setStyleSheet("color: #ffffff; background: transparent;")
        layout.addWidget(self._label)
        layout.addStretch(1)

        self._update_label()

    def date(self) -> date:
        return self._date

    def setDate(self, value: date) -> None:
        self._date = value
        self._update_label()

    def _update_label(self) -> None:
        self._label.setText(self._date.strftime("%Y/%m/%d"))

    def mousePressEvent(self, event) -> None:
        picker = MiniCalendarPicker(initial_dates=[self._date], anchor_date=self._date, mode="single", parent=self)
        if picker.exec() == QDialog.DialogCode.Accepted:
            selected = picker.selected_dates()
            if selected:
                self.setDate(selected[0])
                self.dateChanged.emit(self._date)
        event.accept()
