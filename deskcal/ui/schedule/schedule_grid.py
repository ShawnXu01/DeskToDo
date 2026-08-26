"""紧凑组件和完整课表窗口共用的时间×星期自绘网格。"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget

from deskcal.core.schedule_models import (
    CourseEntry,
    Term,
    compute_visible_minutes,
    minutes_since_midnight,
    split_course_code,
)

GRID_LINE = QColor(255, 255, 255, 38)
GRID_LINE_MINOR = QColor(255, 255, 255, 18)
TEXT_PRIMARY = QColor("#f2f2f2")
TEXT_MUTED = QColor("#a8a8a8")
COURSE_TEXT = QColor("#102a43")
CURRENT_DAY = QColor("#123d70")
CURRENT_TIME = QColor("#ef4035")


def format_hour(minutes: int, use_24_hour: bool = False) -> str:
    hour = (minutes // 60) % 24
    if use_24_hour:
        return f"{hour:02d}:00"
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}{suffix}"


def assign_course_lanes(courses: list[CourseEntry]) -> dict[str, tuple[int, int]]:
    """给同一天有时间重叠的课程分栏，返回 course_id -> (lane, lane_count)。"""
    ordered = sorted(courses, key=lambda c: (c.start_time, c.end_time, c.code.casefold()))
    result: dict[str, tuple[int, int]] = {}
    group: list[CourseEntry] = []
    group_end = -1

    def assign_group(items: list[CourseEntry]) -> None:
        lane_ends: list[int] = []
        lanes: dict[str, int] = {}
        for item in items:
            start = minutes_since_midnight(item.start_time)
            end = minutes_since_midnight(item.end_time)
            lane = next((index for index, lane_end in enumerate(lane_ends) if lane_end <= start), None)
            if lane is None:
                lane = len(lane_ends)
                lane_ends.append(end)
            else:
                lane_ends[lane] = end
            lanes[item.id] = lane
        lane_count = max(1, len(lane_ends))
        for course_id, lane in lanes.items():
            result[course_id] = (lane, lane_count)

    for course in ordered:
        start = minutes_since_midnight(course.start_time)
        end = minutes_since_midnight(course.end_time)
        if group and start >= group_end:
            assign_group(group)
            group = []
            group_end = -1
        group.append(course)
        group_end = max(group_end, end)
    if group:
        assign_group(group)
    return result


class ScheduleGrid(QWidget):
    courseClicked = pyqtSignal(str)
    emptyClicked = pyqtSignal()

    def __init__(self, *, compact: bool, show_weekends: bool = False, use_24_hour: bool = False, parent=None):
        super().__init__(parent)
        self._compact = compact
        self._show_weekends = show_weekends
        self._use_24_hour = use_24_hour
        self._term: Optional[Term] = None
        self._selected_course_id: Optional[str] = None
        self._course_hits: list[tuple[QRectF, CourseEntry]] = []
        self._start_minutes = 8 * 60
        self._end_minutes = 18 * 60
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._update_height()

    def sizeHint(self) -> QSize:
        return QSize(200 if self._compact else 680, self.height())

    def set_term(self, term: Optional[Term]) -> None:
        self._term = term
        courses = term.courses if term is not None else []
        self._start_minutes, self._end_minutes = compute_visible_minutes(courses)
        self._update_height()
        self.update()

    def set_selected_course(self, course_id: Optional[str]) -> None:
        self._selected_course_id = course_id
        self.update()

    def set_show_weekends(self, show: bool) -> None:
        self._show_weekends = show
        self.update()

    def set_use_24_hour(self, enabled: bool) -> None:
        self._use_24_hour = enabled
        self.update()

    def _update_height(self) -> None:
        if self._is_narrow():
            today = date.today().isoweekday()
            course_count = 0 if self._term is None else sum(today in course.weekdays for course in self._term.courses)
            self.setFixedHeight(max(80, 28 + course_count * 38))
            return
        hours = max(1, (self._end_minutes - self._start_minutes) / 60)
        pixels_per_hour = 42 if self._compact else 64
        self.setFixedHeight(round(hours * pixels_per_hour) + (28 if self._compact else 34))

    def resizeEvent(self, event) -> None:
        was_narrow = self._compact and event.oldSize().width() < 170
        is_narrow = self._is_narrow()
        if was_narrow != is_narrow:
            self._update_height()
        super().resizeEvent(event)

    def _days(self) -> list[int]:
        return list(range(1, 8 if self._show_weekends else 6))

    def _is_narrow(self) -> bool:
        return self._compact and self.width() < 170

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._course_hits = []
        if self._is_narrow():
            self._paint_today_list(painter)
        else:
            self._paint_week_grid(painter)
        painter.end()

    def _paint_week_grid(self, painter: QPainter) -> None:
        days = self._days()
        gutter = 36 if self._compact else 54
        header = 28 if self._compact else 34
        grid_width = max(1, self.width() - gutter)
        col_width = grid_width / len(days)
        grid_height = max(1, self.height() - header)
        total_minutes = self._end_minutes - self._start_minutes

        today = date.today()
        current_day = today.isoweekday()
        in_term = bool(self._term and self._term.start_date <= today <= self._term.end_date)

        header_font = QFont()
        header_font.setPointSize(8 if self._compact else 10)
        header_font.setBold(True)
        painter.setFont(header_font)
        labels = ["M", "T", "W", "T", "F", "S", "S"]
        for index, weekday in enumerate(days):
            cell = QRectF(gutter + index * col_width, 0, col_width, header)
            if in_term and weekday == current_day:
                diameter = min(24 if self._compact else 28, col_width - 4)
                circle = QRectF(cell.center().x() - diameter / 2, cell.center().y() - diameter / 2, diameter, diameter)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(CURRENT_DAY)
                painter.drawEllipse(circle)
            painter.setPen(TEXT_PRIMARY)
            painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, labels[weekday - 1])

        for index in range(len(days) + 1):
            x = gutter + index * col_width
            painter.setPen(QPen(GRID_LINE, 1))
            painter.drawLine(int(x), header, int(x), self.height())

        minute = self._start_minutes
        time_font = QFont()
        time_font.setPointSize(7 if self._compact else 9)
        painter.setFont(time_font)
        while minute <= self._end_minutes:
            y = header + (minute - self._start_minutes) / total_minutes * grid_height
            painter.setPen(QPen(GRID_LINE if minute % 60 == 0 else GRID_LINE_MINOR, 1))
            painter.drawLine(gutter, int(y), self.width(), int(y))
            if minute < self._end_minutes and minute % 60 == 0:
                painter.setPen(TEXT_MUTED)
                painter.drawText(QRectF(0, y - 9, gutter - 4, 18), Qt.AlignmentFlag.AlignRight, format_hour(minute, self._use_24_hour))
            minute += 30

        if self._term is not None:
            for day_index, weekday in enumerate(days):
                day_courses = [course for course in self._term.sorted_courses() if weekday in course.weekdays]
                lanes = assign_course_lanes(day_courses)
                for course in day_courses:
                    lane, lane_count = lanes[course.id]
                    start = minutes_since_midnight(course.start_time)
                    end = minutes_since_midnight(course.end_time)
                    if end <= self._start_minutes or start >= self._end_minutes:
                        continue
                    y1 = header + (max(start, self._start_minutes) - self._start_minutes) / total_minutes * grid_height
                    y2 = header + (min(end, self._end_minutes) - self._start_minutes) / total_minutes * grid_height
                    lane_width = col_width / lane_count
                    rect = QRectF(
                        gutter + day_index * col_width + lane * lane_width + 2,
                        y1 + 2,
                        max(6, lane_width - 4),
                        max(8, y2 - y1 - 4),
                    )
                    self._paint_course(painter, rect, course)

        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute
        if in_term and current_day in days and self._start_minutes <= now_minutes <= self._end_minutes:
            day_index = days.index(current_day)
            y = header + (now_minutes - self._start_minutes) / total_minutes * grid_height
            x1 = gutter + day_index * col_width
            x2 = x1 + col_width
            painter.setPen(QPen(CURRENT_TIME, 2))
            painter.drawLine(int(x1), int(y), int(x2), int(y))
            painter.setBrush(CURRENT_TIME)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(x1 - 3, y - 3, 6, 6))

    def _paint_course(self, painter: QPainter, rect: QRectF, course: CourseEntry) -> None:
        painter.setPen(QPen(QColor("#ffffff") if course.id == self._selected_course_id else QColor(course.color).darker(112), 1))
        painter.setBrush(QColor(course.color))
        painter.drawRoundedRect(rect, 5, 5)

        first, second = split_course_code(course.code)
        font = QFont()
        font.setPointSize(7 if self._compact else 9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(COURSE_TEXT)
        if second and rect.height() >= (26 if self._compact else 32):
            text = f"{first}\n{second}"
        else:
            text = first if rect.height() < 24 else course.code
        painter.drawText(rect.adjusted(2, 1, -2, -1), Qt.AlignmentFlag.AlignCenter, text)
        self._course_hits.append((rect, course))

    def _paint_today_list(self, painter: QPainter) -> None:
        today = date.today()
        header = 28
        painter.setPen(TEXT_PRIMARY)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(4, 0, self.width() - 8, header), Qt.AlignmentFlag.AlignVCenter, today.strftime("%A"))

        courses = [] if self._term is None else [c for c in self._term.sorted_courses() if today.isoweekday() in c.weekdays]
        row_height = 38
        for index, course in enumerate(courses):
            top = header + index * row_height
            painter.setPen(TEXT_MUTED)
            small = QFont()
            small.setPointSize(7)
            painter.setFont(small)
            painter.drawText(QRectF(4, top, 40, row_height), Qt.AlignmentFlag.AlignVCenter, course.start_time.strftime("%I:%M").lstrip("0"))
            rect = QRectF(45, top + 3, max(20, self.width() - 49), row_height - 6)
            self._paint_course(painter, rect, course)
        if not courses:
            painter.setPen(TEXT_MUTED)
            painter.drawText(QRectF(4, header, self.width() - 8, 44), Qt.AlignmentFlag.AlignCenter, "今天没有课程")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        for rect, course in reversed(self._course_hits):
            if rect.contains(event.position()):
                self.courseClicked.emit(course.id)
                event.accept()
                return
        self.emptyClicked.emit()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        for rect, course in reversed(self._course_hits):
            if rect.contains(event.position()):
                details = [course.code]
                if course.title:
                    details.append(course.title)
                details.append(f"{course.start_time.strftime('%H:%M')}–{course.end_time.strftime('%H:%M')}")
                if course.location:
                    details.append(course.location)
                QToolTip.showText(event.globalPosition().toPoint(), "\n".join(details), self)
                return
        QToolTip.hideText()
