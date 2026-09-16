"""点击翻月与连续滚动两种月历视图，以及日期任务交互。"""
from __future__ import annotations

import calendar as calendar_module
from datetime import date, timedelta
from typing import Callable

from PyQt6.QtCore import QEvent, QTimer, Qt
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.models import DatedTask
from deskcal.core.storage import (
    CALENDAR_INTERACTION_CLICK,
    CALENDAR_INTERACTION_SCROLL,
    DEFAULT_CALENDAR_SCROLL_SENSITIVITY,
    TaskStore,
    normalize_calendar_font_scale,
    normalize_calendar_interaction_mode,
    normalize_calendar_scroll_sensitivity,
)
from deskcal.services.lunar_holiday import get_day_lunar_info, get_special_day_label
from deskcal.ui.desktop_overlay.task_chip import TaskChipWidget
from deskcal.ui.dialogs.task_dialog import PRIORITY_COLORS, TaskDialog
from deskcal.ui.style_utils import ElidingLabel, make_scroll_area_transparent

WEEKDAY_HEADER_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

ROWS = 6
COLS = 7

BASE_MONTH_TITLE_SIZE = 16
BASE_NAV_BUTTON_SIZE = 13
BASE_WEEKDAY_SIZE = 12
BASE_DATE_SIZE = 13
BASE_TODAY_BADGE_SIZE = 10
BASE_LUNAR_SIZE = 11
BASE_TASK_SIZE = 13
BASE_SCROLL_MONTH_TITLE_SIZE = 18
BASE_SCROLL_ROW_HEIGHT = 72


def scaled_font_size(base_size: int, scale: int) -> int:
    return max(1, round(base_size * normalize_calendar_font_scale(scale) / 100))


class DayCellWidget(QFrame):
    """单个日期格子：日期数字 + 当天命中任务的可滚动列表。"""

    def __init__(
        self,
        day: date,
        is_current_month: bool,
        is_today: bool,
        font_scale: int,
        on_create_requested: Callable[[date], None],
        on_jump_to_month: Callable[[date], None],
        parent=None,
        on_scroll_requested: Callable | None = None,
    ):
        super().__init__(parent)
        self._day = day
        self._is_current_month = is_current_month
        self._on_create_requested = on_create_requested
        self._on_jump_to_month = on_jump_to_month
        self._font_scale = font_scale
        self._on_scroll_requested = on_scroll_requested

        self.setObjectName("dayCell")
        self.setFrameShape(QFrame.Shape.Box)
        # #dayCell 限定只让外圈边框变亮，否则 QFrame 选择器会级联到内部的 QScrollArea。
        border_color = "#e53935" if is_today else "rgba(255, 255, 255, 160)"
        self.setStyleSheet(
            "QFrame { border: 1px solid rgba(255, 255, 255, 25); background: transparent; }"
            f"QFrame#dayCell {{ border: 2px solid {border_color}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        header_row = QHBoxLayout()
        date_label = QLabel(str(day.day))
        if is_today:
            date_label.setStyleSheet(
                "color: #ffffff; background-color: #e53935; border-radius: 8px;"
                f"padding: 0px 4px; font-size: {scaled_font_size(BASE_DATE_SIZE, font_scale)}px; "
                "font-weight: bold;"
            )
        else:
            date_label.setStyleSheet(
                f"color: #ffffff; font-size: {scaled_font_size(BASE_DATE_SIZE, font_scale)}px; "
                "font-weight: bold;"
            )
        header_row.addWidget(date_label)

        if is_today:
            today_badge = QLabel("今天")
            today_badge.setStyleSheet(
                f"color: #e53935; font-size: {scaled_font_size(BASE_TODAY_BADGE_SIZE, font_scale)}px; "
                "font-weight: bold;"
            )
            header_row.addWidget(today_badge)

        lunar_info = get_day_lunar_info(day)
        special_label = get_special_day_label(day)
        lunar_text = special_label or lunar_info.festival_text or lunar_info.lunar_text
        lunar_label = ElidingLabel(lunar_text)
        is_holiday_label = bool(special_label or lunar_info.festival_text)
        lunar_label.setStyleSheet(
            f"color: {'#ffd54f' if is_holiday_label else '#cccccc'}; "
            f"font-size: {scaled_font_size(BASE_LUNAR_SIZE, font_scale)}px; font-weight: bold;"
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

        if on_scroll_requested is not None:
            scroll_area.viewport().installEventFilter(self)

        if not is_current_month:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.45)
            self.setGraphicsEffect(effect)
            # 让滚动区域对鼠标事件透明，点击非本月格子才能落到 DayCellWidget 自己的 mousePressEvent。
            scroll_area.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def eventFilter(self, watched, event) -> bool:
        if self._on_scroll_requested is not None and event.type() == QEvent.Type.Wheel:
            self._on_scroll_requested(event)
            return True
        return super().eventFilter(watched, event)

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
                font_size=scaled_font_size(BASE_TASK_SIZE, self._font_scale),
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


class ClickCalendarView(QWidget):
    """月历主体：含 年月Header(上月/下月) + 星期表头 + 6x7 格子。"""

    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self._store = store
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._font_scale = 100

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(4, 4, 4, 4)
        self._outer_layout.setSpacing(4)

        header_row = QHBoxLayout()
        self._prev_btn = QPushButton("上月")
        self._next_btn = QPushButton("下月")
        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self._weekday_labels: list[QLabel] = []
        for col, label in enumerate(WEEKDAY_HEADER_LABELS):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(lbl, 0, col)
            self._weekday_labels.append(lbl)
        self._grid_layout.setRowStretch(0, 0)
        for row in range(1, ROWS + 1):
            self._grid_layout.setRowStretch(row, 1)
        self._outer_layout.addWidget(self._grid_widget, 1)

        self._day_cells: list[DayCellWidget] = []
        self._apply_static_font_styles()
        self.render()

    def set_font_scale(self, scale: int) -> None:
        normalized = normalize_calendar_font_scale(scale)
        if normalized == self._font_scale:
            return
        self._font_scale = normalized
        self._apply_static_font_styles()
        self.render()

    def _apply_static_font_styles(self) -> None:
        self._title_label.setStyleSheet(
            f"color: #ffffff; font-size: {scaled_font_size(BASE_MONTH_TITLE_SIZE, self._font_scale)}px; "
            "font-weight: bold;"
        )
        button_size = scaled_font_size(BASE_NAV_BUTTON_SIZE, self._font_scale)
        for button in (self._prev_btn, self._next_btn):
            button.setStyleSheet(f"font-size: {button_size}px;")
        weekday_size = scaled_font_size(BASE_WEEKDAY_SIZE, self._font_scale)
        for label in self._weekday_labels:
            label.setStyleSheet(
                f"color: #dddddd; font-size: {weekday_size}px; font-weight: bold; background: transparent;"
            )

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

            cell = DayCellWidget(
                day,
                is_current_month,
                is_today,
                self._font_scale,
                self._open_create_dialog,
                self._jump_to_month,
            )

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


def shifted_month(year: int, month: int, offset: int) -> tuple[int, int]:
    """返回相对指定年月偏移后的年月，供连续月历按块扩展。"""
    absolute_month = year * 12 + month - 1 + offset
    target_year, zero_based_month = divmod(absolute_month, 12)
    return target_year, zero_based_month + 1


class ScrollMonthOpacityEffect(QGraphicsOpacityEffect):
    """用月份局部坐标缓存，避免透明窗口滚动后复用旧屏幕位置和裁剪区域。"""

    def draw(self, painter) -> None:
        pixmap, offset = self.sourcePixmap(
            Qt.CoordinateSystem.LogicalCoordinates,
            QGraphicsOpacityEffect.PixmapPadMode.NoPad,
        )
        if pixmap.isNull():
            return
        painter.save()
        painter.setOpacity(painter.opacity() * self.opacity())
        painter.drawPixmap(offset, pixmap)
        painter.restore()


class ScrollMonthSection(QWidget):
    """连续滚动月历中的一个独立月份，不混入相邻月份日期。"""

    def __init__(
        self,
        year: int,
        month: int,
        store: TaskStore,
        font_scale: int,
        row_height: int,
        on_create_requested: Callable[[date], None],
        on_edit_requested: Callable[[DatedTask], None],
        on_save_requested: Callable[[], None],
        on_scroll_requested: Callable,
        defer_render: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.year = year
        self.month = month
        self._store = store
        self._font_scale = font_scale
        self._row_height = row_height
        self._week_count = 0
        self._on_create_requested = on_create_requested
        self._on_edit_requested = on_edit_requested
        self._on_save_requested = on_save_requested
        self._on_scroll_requested = on_scroll_requested
        self._day_cells: list[DayCellWidget] = []
        self._placeholders: list[QWidget] = []
        self._pending_slots: list[int] = []
        self._pending_slot_index = 0
        self._pending_today = date.today()
        self._pending_tasks: list[DatedTask] = []
        self._pending_first_weekday = 0
        self._pending_days_in_month = 0
        self._opacity = 1.0

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 10, 4, 18)
        self._layout.setSpacing(8)

        title_row = QHBoxLayout()
        self._title_label = QLabel()
        title_row.addWidget(self._title_label)
        title_row.addStretch(1)
        self._layout.addLayout(title_row)

        self._divider = QFrame()
        self._divider.setFixedHeight(1)
        self._divider.setStyleSheet("background: rgba(255, 255, 255, 55); border: none;")
        self._layout.addWidget(self._divider)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setHorizontalSpacing(2)
        self._grid_layout.setVerticalSpacing(2)
        for col in range(COLS):
            self._grid_layout.setColumnStretch(col, 1)
        self._layout.addWidget(self._grid_widget)

        self._opacity_effect = ScrollMonthOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if defer_render:
            self._prepare_render()
        else:
            self.render()

    @property
    def key(self) -> tuple[int, int]:
        return self.year, self.month

    def set_opacity(self, opacity: float) -> None:
        normalized = max(0.0, min(1.0, opacity))
        if abs(normalized - self._opacity) < 0.01:
            return
        self._opacity = normalized
        self._opacity_effect.setOpacity(normalized)

    def set_font_scale(self, scale: int) -> None:
        normalized = normalize_calendar_font_scale(scale)
        if normalized == self._font_scale:
            return
        self._font_scale = normalized
        self.render()

    def set_row_height(self, row_height: int) -> None:
        normalized = max(48, row_height)
        if normalized == self._row_height:
            self.sync_height_to_content()
            return
        self._row_height = normalized
        for row in range(self._week_count):
            self._grid_layout.setRowMinimumHeight(row, normalized)
        for cell in self._day_cells:
            cell.setFixedHeight(normalized)
        for placeholder in self._placeholders:
            placeholder.setFixedHeight(normalized)
        self.sync_height_to_content()

    def sync_height_to_content(self) -> None:
        """宽度或滚动条状态变化后，以布局的真实高度重新锁定月份块。"""
        margins = self._layout.contentsMargins()
        grid_height = (
            self._week_count * self._row_height
            + max(0, self._week_count - 1) * self._grid_layout.verticalSpacing()
        )
        required_height = (
            margins.top()
            + margins.bottom()
            + self._title_label.sizeHint().height()
            + self._divider.height()
            + grid_height
            + self._layout.spacing() * 2
        )
        self.setFixedHeight(required_height)

    def _prepare_render(self) -> None:
        self._title_label.setText(f"{self.year}年{self.month}月")
        self._title_label.setStyleSheet(
            f"color: #ffffff; font-size: {scaled_font_size(BASE_SCROLL_MONTH_TITLE_SIZE, self._font_scale)}px; "
            "font-weight: bold;"
        )

        for cell in self._day_cells:
            self._grid_layout.removeWidget(cell)
            cell.deleteLater()
        for placeholder in self._placeholders:
            self._grid_layout.removeWidget(placeholder)
            placeholder.deleteLater()
        self._day_cells = []
        self._placeholders = []

        first_weekday, days_in_month = calendar_module.monthrange(self.year, self.month)
        week_count = (first_weekday + days_in_month + COLS - 1) // COLS
        self._week_count = week_count
        for row in range(week_count):
            self._grid_layout.setRowMinimumHeight(row, self._row_height)
            self._grid_layout.setRowStretch(row, 0)

        self._pending_first_weekday = first_weekday
        self._pending_days_in_month = days_in_month
        self._pending_today = date.today()
        self._pending_tasks = list(self._store.iter_active_dated_tasks())
        self._pending_slots = list(range(week_count * COLS))
        self._pending_slot_index = 0
        self.sync_height_to_content()

    def _render_slot(self, slot: int) -> None:
        row, col = divmod(slot, COLS)
        day_number = slot - self._pending_first_weekday + 1
        if not 1 <= day_number <= self._pending_days_in_month:
            placeholder = QWidget()
            placeholder.setFixedHeight(self._row_height)
            placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._grid_layout.addWidget(placeholder, row, col)
            self._placeholders.append(placeholder)
            return

        day = date(self.year, self.month, day_number)
        cell = DayCellWidget(
            day,
            True,
            day == self._pending_today,
            self._font_scale,
            self._on_create_requested,
            lambda _day: None,
            on_scroll_requested=self._on_scroll_requested,
        )
        cell.setFixedHeight(self._row_height)
        day_tasks = [task for task in self._pending_tasks if task.recurrence.occurs_on(day)]
        day_tasks.sort(key=lambda task: task.sort_key(day))
        cell.set_tasks(day_tasks, self._on_edit_requested, self._on_save_requested)
        self._grid_layout.addWidget(cell, row, col)
        self._day_cells.append(cell)

    def build_render_batch(self, batch_size: int) -> bool:
        end = min(len(self._pending_slots), self._pending_slot_index + batch_size)
        while self._pending_slot_index < end:
            self._render_slot(self._pending_slots[self._pending_slot_index])
            self._pending_slot_index += 1
        complete = self._pending_slot_index >= len(self._pending_slots)
        if complete:
            self._pending_tasks = []
            self.sync_height_to_content()
        return complete

    def render(self) -> None:
        self._prepare_render()
        self.build_render_batch(len(self._pending_slots))

    def tour_target_cell(self) -> DayCellWidget | None:
        today = date.today()
        return next(
            (cell for cell in self._day_cells if cell._day == today),
            self._day_cells[0] if self._day_cells else None,
        )


class ScrollCalendarView(QWidget):
    """按像素连续滚动、按月份独立分块的方案 B 月历。"""

    _EDGE_THRESHOLD = 180
    _PREFETCH_BATCH_SIZE = 4
    _RETURN_TO_CURRENT_DELAY_MS = 15_000

    def __init__(
        self,
        store: TaskStore,
        font_scale: int = 100,
        scroll_sensitivity: int = DEFAULT_CALENDAR_SCROLL_SENSITIVITY,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._font_scale = normalize_calendar_font_scale(font_scale)
        self._scroll_sensitivity = normalize_calendar_scroll_sensitivity(scroll_sensitivity)
        self._wheel_remainder = 0.0
        self._row_height = BASE_SCROLL_ROW_HEIGHT
        self._sections: list[ScrollMonthSection] = []
        self._positioned = False
        self._extending = False
        self._pending_section: ScrollMonthSection | None = None
        self._pending_direction: str | None = None
        self._opacity_update_pending = False
        today = date.today()
        self._initial_key = (today.year, today.month)
        self._return_to_current_timer = QTimer(self)
        self._return_to_current_timer.setSingleShot(True)
        self._return_to_current_timer.setInterval(self._RETURN_TO_CURRENT_DELAY_MS)
        self._return_to_current_timer.timeout.connect(self._return_to_current_month)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._weekday_widget = QWidget()
        weekday_layout = QGridLayout(self._weekday_widget)
        weekday_layout.setContentsMargins(4, 0, 4, 0)
        weekday_layout.setHorizontalSpacing(2)
        self._weekday_labels: list[QLabel] = []
        for col, text in enumerate(WEEKDAY_HEADER_LABELS):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            weekday_layout.setColumnStretch(col, 1)
            weekday_layout.addWidget(label, 0, col)
            self._weekday_labels.append(label)
        layout.addWidget(self._weekday_widget)

        self._scroll_area = QScrollArea()
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setWidgetResizable(True)
        make_scroll_area_transparent(self._scroll_area)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll_area.setWidget(self._content)
        self._scroll_area.viewport().installEventFilter(self)
        layout.addWidget(self._scroll_area, 1)

        for offset in range(-2, 4):
            self._append_section(*shifted_month(today.year, today.month, offset))

        scroll_bar = self._scroll_area.verticalScrollBar()
        scroll_bar.valueChanged.connect(self._on_scroll_value_changed)
        scroll_bar.actionTriggered.connect(self._on_scroll_action)
        self._apply_static_font_styles()
        self._sync_content_height()
        QTimer.singleShot(0, self._apply_row_height_from_viewport)
        QTimer.singleShot(0, self.ensure_initial_position)

    def _new_section(
        self,
        year: int,
        month: int,
        defer_render: bool = False,
    ) -> ScrollMonthSection:
        return ScrollMonthSection(
            year,
            month,
            self._store,
            self._font_scale,
            self._row_height,
            self._open_create_dialog,
            self._open_edit_dialog,
            self._save_and_rerender,
            self._scroll_by_wheel,
            defer_render,
        )

    def _install_wheel_forwarding(self, root: QWidget) -> None:
        root.installEventFilter(self)
        for child in root.findChildren(QWidget):
            child.installEventFilter(self)

    def _append_section(self, year: int, month: int) -> None:
        section = self._new_section(year, month)
        self._content_layout.addWidget(section)
        self._sections.append(section)
        self._install_wheel_forwarding(section)

    def _apply_static_font_styles(self) -> None:
        weekday_size = scaled_font_size(BASE_WEEKDAY_SIZE, self._font_scale)
        for label in self._weekday_labels:
            label.setStyleSheet(
                f"color: #dddddd; font-size: {weekday_size}px; font-weight: bold; background: transparent;"
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_scroll_area"):
            return
        self._apply_row_height_from_viewport()

    def _apply_row_height_from_viewport(self) -> None:
        target_height = max(48, round((self.height() - 72) / ROWS))
        if target_height == self._row_height:
            self._sync_content_height()
            self._update_section_opacity()
            return
        centered_section = self._centered_section() if self._positioned else None
        centered_key = centered_section.key if centered_section is not None else None
        self._row_height = target_height
        for section in self._sections:
            section.set_row_height(target_height)
        self._sync_content_height()

        if centered_key is not None:
            target = next((section for section in self._sections if section.key == centered_key), None)
            if target is not None:
                self._center_section(target)
        self._update_section_opacity()

    def _sync_content_height(self) -> None:
        for section in self._sections:
            section.sync_height_to_content()
        self._sync_content_container_height()
        self._content_layout.invalidate()
        self._content_layout.activate()

    def _sync_content_container_height(self) -> None:
        margins = self._content_layout.contentsMargins()
        section_height = sum(section.height() for section in self._sections)
        spacing_height = self._content_layout.spacing() * max(0, len(self._sections) - 1)
        required_height = margins.top() + margins.bottom() + section_height + spacing_height
        self._content.setMinimumHeight(0)
        self._content.setMinimumHeight(required_height)

    def ensure_initial_position(self) -> None:
        if self._positioned:
            return
        self._sync_content_height()
        target = next((section for section in self._sections if section.key == self._initial_key), None)
        if target is None or self._scroll_area.viewport().height() <= 0:
            QTimer.singleShot(0, self.ensure_initial_position)
            return
        self._content_layout.activate()
        self._center_section(target)
        self._positioned = True
        self._update_section_opacity()

    def _center_section(self, section: ScrollMonthSection) -> None:
        bar = self._scroll_area.verticalScrollBar()
        target_value = section.y() + section.height() // 2 - self._scroll_area.viewport().height() // 2
        bar.setValue(max(bar.minimum(), min(bar.maximum(), target_value)))

    def eventFilter(self, watched, event) -> bool:
        is_calendar_child = watched is self._scroll_area.viewport() or (
            isinstance(watched, QWidget) and self._content.isAncestorOf(watched)
        )
        if is_calendar_child and event.type() == QEvent.Type.Wheel:
            self._scroll_by_wheel(event)
            return True
        return super().eventFilter(watched, event)

    def set_scroll_sensitivity(self, value: int) -> None:
        self._scroll_sensitivity = normalize_calendar_scroll_sensitivity(value)
        self._wheel_remainder = 0.0

    def _restart_return_to_current_timer(self) -> None:
        self._return_to_current_timer.start()

    def _on_scroll_action(self, _action: int) -> None:
        self._restart_return_to_current_timer()
        QTimer.singleShot(0, self._maybe_prefetch)

    def _return_to_current_month(self) -> None:
        if self._extending:
            self._return_to_current_timer.start(250)
            return
        today = date.today()
        current_key = (today.year, today.month)
        target = next((section for section in self._sections if section.key == current_key), None)
        if target is None:
            target = next((section for section in self._sections if section.key == self._initial_key), None)
        if target is not None:
            self._center_section(target)
            self._update_section_opacity()

    def _scroll_by_wheel(self, event) -> None:
        self._restart_return_to_current_timer()
        pixel_delta = event.pixelDelta().y()
        raw_delta = pixel_delta if pixel_delta else event.angleDelta().y() / 120 * 72
        scaled_delta = raw_delta * self._scroll_sensitivity / 100 + self._wheel_remainder
        delta = int(scaled_delta)
        self._wheel_remainder = scaled_delta - delta
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.value() - delta)
        self._maybe_prefetch("before" if delta > 0 else "after")
        event.accept()

    def _on_scroll_value_changed(self, value: int) -> None:
        self._schedule_opacity_update()

    def _schedule_opacity_update(self) -> None:
        """把同一轮事件中的多次滚动合并，避免透明度重绘阻塞滚轮事件。"""
        if self._opacity_update_pending:
            return
        self._opacity_update_pending = True
        QTimer.singleShot(0, self._run_scheduled_opacity_update)

    def _run_scheduled_opacity_update(self) -> None:
        self._opacity_update_pending = False
        self._update_section_opacity()

    def _maybe_prefetch(self, preferred_direction: str | None = None) -> None:
        if not self._positioned or self._extending or self._pending_section is not None:
            return
        bar = self._scroll_area.verticalScrollBar()
        top_buffer = bar.value()
        bottom_buffer = bar.maximum() - bar.value()
        threshold = max(self._EDGE_THRESHOLD, self._scroll_area.viewport().height() * 2)
        buffers = {"before": top_buffer, "after": bottom_buffer}
        if preferred_direction is not None:
            if buffers[preferred_direction] <= threshold:
                self._start_prefetch(preferred_direction)
            return
        direction = min(buffers, key=buffers.get)
        if buffers[direction] > threshold:
            return
        self._start_prefetch(direction)

    def _start_prefetch(self, direction: str) -> None:
        if self._pending_section is not None:
            return
        if direction == "before":
            year, month = shifted_month(*self._sections[0].key, -1)
        else:
            year, month = shifted_month(*self._sections[-1].key, 1)
        self._extending = True
        self._pending_direction = direction
        self._pending_section = self._new_section(year, month, defer_render=True)
        QTimer.singleShot(0, self._build_prefetch_batch)

    def _build_prefetch_batch(self) -> None:
        section = self._pending_section
        if section is None:
            return
        if not section.build_render_batch(self._PREFETCH_BATCH_SIZE):
            QTimer.singleShot(0, self._build_prefetch_batch)
            return
        self._install_wheel_forwarding(section)
        if self._pending_direction == "before":
            self._finish_prefetch_before(section)
        else:
            self._finish_prefetch_after(section)

    def _finish_prefetch_before(self, section: ScrollMonthSection) -> None:
        self._scroll_area.viewport().setUpdatesEnabled(False)
        bar = self._scroll_area.verticalScrollBar()
        old_value = bar.value()
        self._content_layout.insertWidget(0, section)
        self._sections.insert(0, section)
        self._sync_content_container_height()
        inserted_extent = section.height() + self._content_layout.spacing()
        target_value = old_value + inserted_extent

        def finish(attempt: int = 0) -> None:
            self._sync_content_container_height()
            if bar.maximum() < target_value and attempt < 4:
                QTimer.singleShot(0, lambda: finish(attempt + 1))
                return
            bar.setValue(min(target_value, bar.maximum()))
            self._scroll_area.viewport().setUpdatesEnabled(True)
            self._scroll_area.viewport().update()
            self._finish_prefetch()

        QTimer.singleShot(0, finish)

    def _finish_prefetch_after(self, section: ScrollMonthSection) -> None:
        self._content_layout.addWidget(section)
        self._sections.append(section)
        self._sync_content_container_height()
        QTimer.singleShot(0, self._finish_prefetch)

    def _finish_prefetch(self) -> None:
        self._sync_content_container_height()
        self._pending_section = None
        self._pending_direction = None
        self._extending = False
        self._update_section_opacity()

    def _update_section_opacity(self) -> None:
        if not self._sections:
            return
        bar = self._scroll_area.verticalScrollBar()
        viewport_height = max(1, self._scroll_area.viewport().height())
        viewport_center = bar.value() + viewport_height / 2
        full_opacity_distance = viewport_height * 0.38
        fade_distance = viewport_height * 0.75
        for section in self._sections:
            distance = abs(section.y() + section.height() / 2 - viewport_center)
            if distance <= full_opacity_distance:
                opacity = 1.0
            else:
                progress = min(1.0, (distance - full_opacity_distance) / fade_distance)
                opacity = 1.0 - progress * 0.58
            section.set_opacity(opacity)

    def _centered_section(self) -> ScrollMonthSection | None:
        if not self._sections:
            return None
        bar = self._scroll_area.verticalScrollBar()
        center = bar.value() + self._scroll_area.viewport().height() / 2
        return min(self._sections, key=lambda section: abs(section.y() + section.height() / 2 - center))

    def set_font_scale(self, scale: int) -> None:
        normalized = normalize_calendar_font_scale(scale)
        if normalized == self._font_scale:
            return
        centered_section = self._centered_section()
        centered_key = centered_section.key if centered_section is not None else self._initial_key
        self._font_scale = normalized
        self._apply_static_font_styles()
        for section in self._sections:
            section.set_font_scale(normalized)
            self._install_wheel_forwarding(section)

        def restore_center() -> None:
            target = next((section for section in self._sections if section.key == centered_key), None)
            if target is not None:
                self._center_section(target)
            self._update_section_opacity()

        QTimer.singleShot(0, restore_center)

    def _open_create_dialog(self, day: date) -> None:
        dialog = TaskDialog(self._store, default_date=day, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render()

    def _open_edit_dialog(self, task: DatedTask) -> None:
        dialog = TaskDialog(self._store, existing_task=task, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render()

    def _save_and_rerender(self) -> None:
        self._store.save()
        self.render()

    def render(self) -> None:
        for section in self._sections:
            section.render()
            self._install_wheel_forwarding(section)
        QTimer.singleShot(0, self._update_section_opacity)

    def tour_target_cell(self) -> DayCellWidget | None:
        today = date.today()
        today_section = next(
            (section for section in self._sections if section.key == (today.year, today.month)),
            None,
        )
        target_section = today_section or self._centered_section()
        return target_section.tour_target_cell() if target_section is not None else None


class CalendarGrid(QWidget):
    """在原点击月历和新增连续滚动月历之间切换的稳定外层。"""

    def __init__(
        self,
        store: TaskStore,
        interaction_mode: str = CALENDAR_INTERACTION_CLICK,
        scroll_sensitivity: int = DEFAULT_CALENDAR_SCROLL_SENSITIVITY,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._font_scale = 100
        self._interaction_mode = CALENDAR_INTERACTION_CLICK
        self._scroll_sensitivity = normalize_calendar_scroll_sensitivity(scroll_sensitivity)
        self._scroll_view: ScrollCalendarView | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._click_view = ClickCalendarView(store)
        self._stack.addWidget(self._click_view)
        self.set_interaction_mode(interaction_mode)

    @property
    def interaction_mode(self) -> str:
        return self._interaction_mode

    def _ensure_scroll_view(self) -> ScrollCalendarView:
        if self._scroll_view is None:
            self._scroll_view = ScrollCalendarView(
                self._store,
                self._font_scale,
                self._scroll_sensitivity,
            )
            self._stack.addWidget(self._scroll_view)
        return self._scroll_view

    def set_interaction_mode(self, mode: str) -> None:
        normalized = normalize_calendar_interaction_mode(mode)
        self._interaction_mode = normalized
        if normalized == CALENDAR_INTERACTION_SCROLL:
            target = self._ensure_scroll_view()
            self._stack.setCurrentWidget(target)
            target.render()
            QTimer.singleShot(0, target.ensure_initial_position)
        else:
            self._stack.setCurrentWidget(self._click_view)
            self._click_view.render()

    def set_font_scale(self, scale: int) -> None:
        self._font_scale = normalize_calendar_font_scale(scale)
        self._click_view.set_font_scale(self._font_scale)
        if self._scroll_view is not None:
            self._scroll_view.set_font_scale(self._font_scale)

    def set_scroll_sensitivity(self, value: int) -> None:
        self._scroll_sensitivity = normalize_calendar_scroll_sensitivity(value)
        if self._scroll_view is not None:
            self._scroll_view.set_scroll_sensitivity(self._scroll_sensitivity)

    def render(self) -> None:
        current = self._stack.currentWidget()
        if isinstance(current, (ClickCalendarView, ScrollCalendarView)):
            current.render()

    def tour_target_cell(self) -> DayCellWidget | None:
        current = self._stack.currentWidget()
        if isinstance(current, (ClickCalendarView, ScrollCalendarView)):
            return current.tour_target_cell()
        return None
