"""进度条组件：容器型，内部多条目，按起止日期算百分比，到达终止日期后封顶 100%。"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from deskcal.ui.style_utils import ElidingLabel

ROW_HEIGHT = 44
BAR_HEIGHT = 6
REFRESH_INTERVAL_MS = 60_000

TRACK_COLOR = QColor(255, 255, 255, 50)
FILL_COLOR = QColor(255, 255, 255, 230)


def default_progress_config() -> dict:
    return {"items": []}


def compute_percent(start: date, end: date, today: date) -> int:
    if today >= end:
        return 100
    if today <= start:
        return 0
    total_days = (end - start).days
    if total_days <= 0:
        return 100
    elapsed_days = (today - start).days
    return min(100, max(0, round(elapsed_days / total_days * 100)))


class ThinProgressBar(QWidget):
    """细长白色进度条：半透明白底打底，已走过部分用不透明白色覆盖。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(BAR_HEIGHT)
        self._percent = 0

    def setValue(self, percent: int) -> None:
        self._percent = percent
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.height() / 2

        track_rect = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(TRACK_COLOR)
        painter.drawRoundedRect(track_rect, radius, radius)

        fill_width = self.width() * self._percent / 100
        if fill_width > 0:
            fill_rect = QRectF(0, 0, fill_width, self.height())
            painter.setBrush(FILL_COLOR)
            painter.drawRoundedRect(fill_rect, radius, radius)
        painter.end()


class ProgressWidget(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)

        self._rows: list[tuple[ThinProgressBar, QLabel, str, str]] = []  # (bar, percent label, start ISO, end ISO)
        self._build_rows()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(REFRESH_INTERVAL_MS)

    def _build_rows(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []

        for item in self._config.get("items", []):
            row = QWidget()
            row.setFixedHeight(ROW_HEIGHT)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            title_row = QHBoxLayout()
            title_label = ElidingLabel(item["title"])
            title_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; background: transparent;")
            percent_label = QLabel()
            percent_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; background: transparent;")
            title_row.addWidget(title_label, 1)
            title_row.addWidget(percent_label)
            row_layout.addLayout(title_row)

            bar = ThinProgressBar()
            row_layout.addWidget(bar)

            self._layout.addWidget(row)
            self._rows.append((bar, percent_label, item["start"], item["end"]))

        self._tick()

    def _tick(self) -> None:
        today = date.today()
        for bar, percent_label, start_iso, end_iso in self._rows:
            start = date.fromisoformat(start_iso)
            end = date.fromisoformat(end_iso)
            percent = compute_percent(start, end, today)
            bar.setValue(percent)
            percent_label.setText(f"{percent}%")
