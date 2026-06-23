"""迷你月历弹窗：multi 模式用于"指定多日"勾选多个离散日期；single 模式用于单个日期选择（点击即确定）。"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Literal, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from deskcal.utils.icons import app_icon

WEEKEND_COLUMNS = {5, 6}  # 列 0=周一 ... 5=周六 6=周日

# 弹窗是独立的顶层 QDialog，不会继承父级（TaskDialog/ConfigWindow）的样式表，
# 必须显式给暗色主题，否则会用系统默认白底白窗渲染。
QSS = """
QDialog { background-color: #202020; }
QLabel { color: #ffffff; background: transparent; }
QPushButton {
    background-color: #3a3a3a;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:checked { background-color: #2196f3; }
"""

WEEKEND_BUTTON_STYLE = (
    "QPushButton { background-color: #3a3a3a; color: #e53935; border: none; border-radius: 4px; }"
    "QPushButton:hover { background-color: #4a4a4a; }"
    "QPushButton:checked { background-color: #2196f3; color: #ffffff; }"
)

YEAR_PICK_RANGE = 3  # 当前年份前后各 3 年


class _YearMonthPicker(QDialog):
    """年/月快速选择的小弹窗，竖向排列，跟下面的日期网格用同一套暗色风格。"""

    def __init__(self, options: list[int], current: int, suffix: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"选择{suffix}")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(QSS)
        self._chosen: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)
        for value in options:
            btn = QPushButton(f"{value}{suffix}")
            btn.setCheckable(True)
            btn.setChecked(value == current)
            btn.clicked.connect(lambda _checked=False, v=value: self._choose(v))
            layout.addWidget(btn)

    def _choose(self, value: int) -> None:
        self._chosen = value
        self.accept()

    def chosen(self) -> Optional[int]:
        return self._chosen


class MiniCalendarPicker(QDialog):
    """7x6 网格日期选择。multi 模式多选+确认；single 模式点击某天即确定并关闭。"""

    def __init__(
        self,
        initial_dates: Optional[list[date]] = None,
        anchor_date: Optional[date] = None,
        mode: Literal["single", "multi"] = "multi",
        parent=None,
    ):
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("选择日期")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(QSS)
        self.setMinimumWidth(252)

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
        self._year_btn = QPushButton()
        self._year_btn.clicked.connect(self._pick_year)
        self._month_btn = QPushButton()
        self._month_btn.clicked.connect(self._pick_month)
        prev_btn.clicked.connect(self._go_prev_month)
        next_btn.clicked.connect(self._go_next_month)
        nav_layout.addWidget(prev_btn)
        nav_layout.addWidget(self._year_btn, 1)
        nav_layout.addWidget(self._month_btn, 1)
        nav_layout.addWidget(next_btn)
        layout.addLayout(nav_layout)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(2)
        layout.addWidget(self._grid_widget)

        self._button_row = QHBoxLayout()
        if self._mode == "multi":
            clear_btn = QPushButton("清除")
            confirm_btn = QPushButton("确定")
            clear_btn.clicked.connect(self._clear_selection)
            confirm_btn.clicked.connect(self.accept)
            self._button_row.addWidget(clear_btn)
            self._button_row.addStretch(1)
            self._button_row.addWidget(confirm_btn)
            layout.addLayout(self._button_row)

        self._render_month()
        # 6 行月份（如 31 天且 1 号是周六/周日）也要完整显示，不用固定尺寸，按内容自适应。
        self.adjustSize()

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

    def _pick_year(self) -> None:
        options = list(range(self._year - YEAR_PICK_RANGE, self._year + YEAR_PICK_RANGE + 1))
        picker = _YearMonthPicker(options, self._year, "年", parent=self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.chosen() is not None:
            self._year = picker.chosen()
            self._render_month()

    def _pick_month(self) -> None:
        picker = _YearMonthPicker(list(range(1, 13)), self._month, "月", parent=self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.chosen() is not None:
            self._month = picker.chosen()
            self._render_month()

    def _render_month(self) -> None:
        self._year_btn.setText(f"{self._year}年")
        self._month_btn.setText(f"{self._month}月")

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
            btn.setFixedSize(30, 30)
            if col in WEEKEND_COLUMNS:
                btn.setStyleSheet(WEEKEND_BUTTON_STYLE)
            btn.clicked.connect(lambda checked, d=day: self._toggle_day(d, checked))
            self._grid_layout.addWidget(btn, row, col)

        self.adjustSize()

    def _toggle_day(self, day: date, checked: bool) -> None:
        if self._mode == "single":
            self._selected = {day} if checked else set()
            if checked:
                self.accept()
            return

        if checked:
            self._selected.add(day)
        else:
            self._selected.discard(day)
