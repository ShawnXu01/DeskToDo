"""迷你月历多选弹窗：用于周期类型"指定多日"时挑选若干离散日期。"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MiniCalendarPicker(QDialog):
    """7x6 网格多选，确认后通过 selected_dates() 取结果，取消则保持原有选择不变。"""

    def __init__(
        self,
        initial_dates: Optional[list[date]] = None,
        anchor_date: Optional[date] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("选择日期")
        self.setFixedSize(260, 260)

        self._selected: set[date] = set(initial_dates or [])
        anchor = anchor_date or (min(self._selected) if self._selected else date.today())
        self._year = anchor.year
        self._month = anchor.month

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("<")
        next_btn = QPushButton(">")
        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_btn.clicked.connect(self._go_prev_month)
        next_btn.clicked.connect(self._go_next_month)
        nav_layout.addWidget(prev_btn)
        nav_layout.addWidget(self._title_label, 1)
        nav_layout.addWidget(next_btn)
        layout.addLayout(nav_layout)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(2)
        layout.addWidget(self._grid_widget)

        button_row = QHBoxLayout()
        clear_btn = QPushButton("清除")
        confirm_btn = QPushButton("确定")
        clear_btn.clicked.connect(self._clear_selection)
        confirm_btn.clicked.connect(self.accept)
        button_row.addWidget(clear_btn)
        button_row.addStretch(1)
        button_row.addWidget(confirm_btn)
        layout.addLayout(button_row)

        self._render_month()

    def selected_dates(self) -> list[date]:
        return sorted(self._selected)

    def _go_prev_month(self) -> None:
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self._render_month()

    def _go_next_month(self) -> None:
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self._render_month()

    def _clear_selection(self) -> None:
        self._selected.clear()
        self._render_month()

    def _render_month(self) -> None:
        self._title_label.setText(f"{self._year}年{self._month}月")

        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        first_weekday, days_in_month = calendar.monthrange(self._year, self._month)
        for day_num in range(1, days_in_month + 1):
            day = date(self._year, self._month, day_num)
            row, col = divmod(first_weekday + day_num - 1, 7)
            btn = QPushButton(str(day_num))
            btn.setCheckable(True)
            btn.setChecked(day in self._selected)
            btn.setFixedSize(28, 28)
            btn.clicked.connect(lambda checked, d=day: self._toggle_day(d, checked))
            self._grid_layout.addWidget(btn, row, col)

    def _toggle_day(self, day: date, checked: bool) -> None:
        if checked:
            self._selected.add(day)
        else:
            self._selected.discard(day)
