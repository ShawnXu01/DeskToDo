"""倒计时组件：容器型，内部多条目，每条固定行高，过期后显示负数。

左侧标题为主、日期为辅（大小字号区分主次），右侧是倒计时剩余时间。
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from deskcal.ui.style_utils import ElidingLabel

ROW_HEIGHT = 44
REFRESH_INTERVAL_MS = 60_000


def default_countdown_config() -> dict:
    return {"items": []}


def format_remaining(delta_seconds: float) -> str:
    sign = "-" if delta_seconds < 0 else ""
    total_minutes = int(abs(delta_seconds) // 60)
    days, rem_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(rem_minutes, 60)
    if days > 0:
        return f"{sign}{days}天{hours}时{minutes}分"
    if hours > 0:
        return f"{sign}{hours}时{minutes}分"
    return f"{sign}{minutes}分"


class CountdownWidget(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        self._rows: list[tuple[QLabel, str]] = []  # (剩余时间 label, deadline ISO 字符串)
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

        items = sorted(self._config.get("items", []), key=lambda it: it["deadline"])
        for item in items:
            row = QWidget()
            row.setFixedHeight(ROW_HEIGHT)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            title_label = ElidingLabel(item["title"])
            title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent;")
            date_text = item["deadline"].split("T")[0]
            date_label = QLabel(date_text)
            date_label.setStyleSheet("color: #aaaaaa; font-size: 10px; background: transparent;")
            text_col.addWidget(title_label)
            text_col.addWidget(date_label)

            remaining_label = QLabel()
            remaining_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; background: transparent;")

            row_layout.addLayout(text_col, 1)
            row_layout.addWidget(remaining_label)

            self._layout.addWidget(row)
            self._rows.append((remaining_label, item["deadline"]))

        self._tick()

    def _tick(self) -> None:
        now = datetime.now()
        for label, deadline_iso in self._rows:
            deadline = datetime.fromisoformat(deadline_iso)
            label.setText(format_remaining((deadline - now).total_seconds()))
