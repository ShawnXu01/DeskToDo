"""7x6 月历主体：渲染当月格子，处理任务的右键新建/双击编辑/勾选完成。"""
from __future__ import annotations

import calendar as calendar_module
from datetime import date, timedelta
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.models import DatedTask
from deskcal.core.storage import TaskStore
from deskcal.services.lunar_holiday import get_day_lunar_info, get_special_day_label
from deskcal.ui.desktop_overlay.task_chip import TaskChipWidget
from deskcal.ui.dialogs.task_dialog import PRIORITY_COLORS, TaskDialog
from deskcal.ui.style_utils import ElidingLabel, make_scroll_area_transparent

WEEKDAY_HEADER_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

ROWS = 6
COLS = 7


class DayCellWidget(QFrame):
    """单个日期格子：日期数字 + 当天命中任务的可滚动列表。"""

    def __init__(
        self,
        day: date,
        is_current_month: bool,
        is_today: bool,
        on_create_requested: Callable[[date], None],
        on_jump_to_month: Callable[[date], None],
        parent=None,
    ):
        super().__init__(parent)
        self._day = day
        self._is_current_month = is_current_month
        self._on_create_requested = on_create_requested
        self._on_jump_to_month = on_jump_to_month

        self.setObjectName("dayCell")
        self.setFrameShape(QFrame.Shape.Box)
        # #dayCell 限定只让外圈边框变亮，否则 QFrame 选择器会级联到内部的 QScrollArea。
        self.setStyleSheet(
            "QFrame { border: 1px solid rgba(255, 255, 255, 25); background: transparent; }"
            "QFrame#dayCell { border: 2px solid rgba(255, 255, 255, 160); }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        header_row = QHBoxLayout()
        date_label = QLabel(str(day.day))
        if is_today:
            date_label.setStyleSheet(
                "color: #ffffff; background-color: #e53935; border-radius: 8px;"
                "padding: 0px 4px; font-size: 13px; font-weight: bold;"
            )
        else:
            date_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        header_row.addWidget(date_label)

        if is_today:
            today_badge = QLabel("今天")
            today_badge.setStyleSheet("color: #e53935; font-size: 10px; font-weight: bold;")
            header_row.addWidget(today_badge)

        lunar_info = get_day_lunar_info(day)
        special_label = get_special_day_label(day)
        lunar_text = special_label or lunar_info.festival_text or lunar_info.lunar_text
        lunar_label = ElidingLabel(lunar_text)
        is_holiday_label = bool(special_label or lunar_info.festival_text)
        lunar_label.setStyleSheet(
            f"color: {'#ffd54f' if is_holiday_label else '#cccccc'}; font-size: 11px; font-weight: bold;"
        )
        lunar_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Ignored 让某一天的长文字不会把所在列顶宽；stretch=1 仍然给它格子里剩余的全部宽度。
        lunar_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header_row.addWidget(lunar_label, 1)

        layout.addLayout(header_row)

        self._tasks_container = QWidget()
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(0, 0, 0, 0)
        self._tasks_layout.setSpacing(0)
        self._tasks_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self._tasks_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        make_scroll_area_transparent(scroll_area)
        layout.addWidget(scroll_area, 1)

        if not is_current_month:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.45)
            self.setGraphicsEffect(effect)
            # 让滚动区域对鼠标事件透明，点击非本月格子才能落到 DayCellWidget 自己的 mousePressEvent。
            scroll_area.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def mousePressEvent(self, event) -> None:
        if not self._is_current_month and event.button() == Qt.MouseButton.LeftButton:
            self._on_jump_to_month(self._day)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_tasks(self, tasks: list[DatedTask], on_edit: Callable[[DatedTask], None], on_save: Callable[[], None]) -> None:
        while self._tasks_layout.count() > 1:
            item = self._tasks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for task in tasks:
            chip = TaskChipWidget(
                name=task.name,
                color=PRIORITY_COLORS[task.priority],
                completed=task.is_completed_on(self._day),
            )
            chip.editRequested.connect(lambda t=task: on_edit(t))

            def _on_toggle(checked: bool, t: DatedTask = task) -> None:
                t.set_completed(self._day, checked)
                on_save()

            chip.toggleCompleteRequested.connect(_on_toggle)
            self._tasks_layout.insertWidget(self._tasks_layout.count() - 1, chip)

    def contextMenuEvent(self, event) -> None:
        self._on_create_requested(self._day)
        event.accept()


class CalendarGrid(QWidget):
    """月历主体：含 年月Header(上月/下月) + 星期表头 + 6x7 格子。"""

    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self._store = store
        today = date.today()
        self._year = today.year
        self._month = today.month

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(4, 4, 4, 4)
        self._outer_layout.setSpacing(4)

        header_row = QHBoxLayout()
        self._prev_btn = QPushButton("上月")
        self._next_btn = QPushButton("下月")
        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        self._prev_btn.clicked.connect(self._go_prev_month)
        self._next_btn.clicked.connect(self._go_next_month)
        header_row.addWidget(self._prev_btn)
        header_row.addWidget(self._title_label, 1)
        header_row.addWidget(self._next_btn)
        self._outer_layout.addLayout(header_row)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(2)
        for col in range(COLS):
            self._grid_layout.setColumnStretch(col, 1)
        # 星期表头放进跟日期格子同一个 QGridLayout 的第 0 行，两者共用同一份列宽分配，
        # 才能保证表头文字永远跟下面的格子列对齐（之前是两个独立布局，宽度可能各算各的）。
        for col, label in enumerate(WEEKDAY_HEADER_LABELS):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #dddddd; font-size: 12px; font-weight: bold; background: transparent;")
            self._grid_layout.addWidget(lbl, 0, col)
        self._grid_layout.setRowStretch(0, 0)
        for row in range(1, ROWS + 1):
            self._grid_layout.setRowStretch(row, 1)
        self._outer_layout.addWidget(self._grid_widget, 1)

        self._day_cells: list[DayCellWidget] = []
        self.render()

    def _go_prev_month(self) -> None:
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self.render()

    def _go_next_month(self) -> None:
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self.render()

    def _jump_to_month(self, day: date) -> None:
        self._year = day.year
        self._month = day.month
        self.render()

    def _open_create_dialog(self, day: date) -> None:
        dialog = TaskDialog(self._store, default_date=day, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render()

    def _open_edit_dialog(self, task: DatedTask) -> None:
        dialog = TaskDialog(self._store, existing_task=task, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render()

    def render(self) -> None:
        self._title_label.setText(f"{self._year}年{self._month}月")

        # 只清掉日期格子（第 1..ROWS 行），第 0 行的星期表头是常驻的，不跟着每次 render 重建。
        for cell in self._day_cells:
            self._grid_layout.removeWidget(cell)
            cell.deleteLater()
        self._day_cells = []

        first_weekday, _ = calendar_module.monthrange(self._year, self._month)
        first_day_of_month = date(self._year, self._month, 1)
        grid_start = first_day_of_month - timedelta(days=first_weekday)

        today = date.today()
        all_dated_tasks = list(self._store.iter_active_dated_tasks())

        for index in range(ROWS * COLS):
            day = grid_start + timedelta(days=index)
            row, col = divmod(index, COLS)
            is_current_month = day.month == self._month and day.year == self._year
            is_today = day == today

            cell = DayCellWidget(day, is_current_month, is_today, self._open_create_dialog, self._jump_to_month)

            day_tasks = [t for t in all_dated_tasks if t.recurrence.occurs_on(day)]
            day_tasks.sort(key=lambda t: t.sort_key(day))
            cell.set_tasks(day_tasks, self._open_edit_dialog, self._save_and_rerender)

            self._grid_layout.addWidget(cell, row + 1, col)
            self._day_cells.append(cell)

    def _save_and_rerender(self) -> None:
        self._store.save()
        self.render()

    def tour_target_cell(self) -> DayCellWidget | None:
        """返回适合首次引导聚光的日期格，优先使用今天。"""
        today = date.today()
        return next(
            (cell for cell in self._day_cells if cell._day == today),
            next((cell for cell in self._day_cells if cell._is_current_month), None),
        )
