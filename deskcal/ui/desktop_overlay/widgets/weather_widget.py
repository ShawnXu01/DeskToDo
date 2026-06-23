"""天气组件：今天+未来3天预报 + 最高/最低温折线图。网络请求放在 QThread 里跑，避免阻塞 UI；
失败时静默保留上一次显示的数据，不弹错误。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from deskcal.services.weather_service import DayForecast, WeatherInfo, get_city_name, get_current_weather, get_forecast
from deskcal.ui.style_utils import ElidingLabel

REFRESH_INTERVAL_MS = 30 * 60 * 1000  # 30 分钟
RELATIVE_TIME_TICK_MS = 30 * 1000
CHART_HEIGHT = 110

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# QWeather 图标代码按百位段分类，映射到 Unicode 天气符号，避免额外引入图标资源依赖。
_ICON_EMOJI_RANGES = [
    (100, 103, "☀️"),
    (104, 199, "☁️"),
    (200, 213, "🌬️"),
    (300, 399, "🌧️"),
    (400, 499, "❄️"),
    (500, 515, "🌫️"),
    (900, 999, "🌡️"),
]


def weather_emoji(icon_code: str) -> str:
    try:
        code = int(icon_code)
    except (TypeError, ValueError):
        return "🌡️"
    for lower, upper, emoji in _ICON_EMOJI_RANGES:
        if lower <= code <= upper:
            return emoji
    return "🌡️"


def default_weather_config() -> dict:
    return {"location": ""}


class _WeatherFetchThread(QThread):
    fetched = pyqtSignal(object, object)  # Optional[WeatherInfo], Optional[list[DayForecast]]

    def __init__(self, location: str, parent=None):
        super().__init__(parent)
        self._location = location

    def run(self) -> None:
        now = get_current_weather(self._location)
        forecast = get_forecast(self._location)
        self.fetched.emit(now, forecast)


class _CityNameFetchThread(QThread):
    fetched = pyqtSignal(object)  # Optional[str]

    def __init__(self, location: str, parent=None):
        super().__init__(parent)
        self._location = location

    def run(self) -> None:
        self.fetched.emit(get_city_name(self._location))


class _TemperatureChart(QWidget):
    """自绘最高/最低温折线图，4 个数据点，不引入图表库依赖。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highs: list[float] = []
        self._lows: list[float] = []
        self.setMinimumHeight(CHART_HEIGHT)

    def set_data(self, highs: list[float], lows: list[float]) -> None:
        self._highs = highs
        self._lows = lows
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if len(self._highs) < 2 or len(self._lows) < 2:
            painter.end()
            return

        # 上下留出文字高度给最高温（折线上方）/最低温（折线下方）的标签用。
        margin_x = 16
        label_space = 16
        width = self.width() - margin_x * 2
        height = self.height() - label_space * 2
        count = len(self._highs)
        step_x = width / (count - 1)

        all_values = self._highs + self._lows
        value_min, value_max = min(all_values), max(all_values)
        value_range = max(value_max - value_min, 1.0)

        def point(index: int, value: float) -> tuple[float, float]:
            x = margin_x + step_x * index
            y = label_space + height - (value - value_min) / value_range * height
            return x, y

        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        series = (
            (self._highs, QColor("#ff7043"), -8),  # 最高温：标签画在折线节点上方
            (self._lows, QColor("#42a5f5"), 14),  # 最低温：标签画在折线节点下方
        )
        for values, color, label_offset_y in series:
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            points = [point(i, v) for i, v in enumerate(values)]
            for i in range(len(points) - 1):
                painter.drawLine(int(points[i][0]), int(points[i][1]), int(points[i + 1][0]), int(points[i + 1][1]))
            for i, (x, y) in enumerate(points):
                painter.drawEllipse(int(x) - 2, int(y) - 2, 4, 4)
                label = f"{values[i]:.0f}°"
                # 按文字宽度居中后再夹到 widget 范围内，避免两端的点的文字被裁掉一半。
                label_width = painter.fontMetrics().horizontalAdvance(label)
                label_x = max(0, min(int(x - label_width / 2), self.width() - label_width))
                painter.drawText(label_x, int(y) + label_offset_y, label)

        painter.end()


class WeatherWidget(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._thread: Optional[_WeatherFetchThread] = None
        self._city_thread: Optional[_CityNameFetchThread] = None
        self._last_update: Optional[datetime] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._city_label = ElidingLabel("")
        self._city_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        self._city_label.setVisible(False)
        layout.addWidget(self._city_label)

        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        self._update_label = QLabel("尚未更新")
        self._update_label.setStyleSheet("color: #cccccc; font-size: 10px; font-weight: bold;")
        header_row.addWidget(self._update_label)
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(26, 26)
        refresh_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        refresh_btn.clicked.connect(self._refresh)
        header_row.addWidget(refresh_btn)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self._days_row = QHBoxLayout()
        self._days_row.setSpacing(2)
        self._day_columns: list[dict[str, QLabel]] = []
        for _ in range(4):
            column_layout, labels = self._build_day_column()
            self._day_columns.append(labels)
            self._days_row.addLayout(column_layout, 1)
        layout.addLayout(self._days_row)

        self._chart = _TemperatureChart()
        layout.addWidget(self._chart)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_INTERVAL_MS)

        self._relative_time_timer = QTimer(self)
        self._relative_time_timer.timeout.connect(self._update_relative_time_label)
        self._relative_time_timer.start(RELATIVE_TIME_TICK_MS)

        self._refresh()
        self._fetch_city_name()

    def _fetch_city_name(self) -> None:
        location = self._config.get("location")
        if not location:
            return
        self._city_thread = _CityNameFetchThread(location, self)
        self._city_thread.fetched.connect(self._on_city_name_fetched)
        self._city_thread.start()

    def _on_city_name_fetched(self, name: Optional[str]) -> None:
        if not name:
            return
        self._city_label.setText(name)
        self._city_label.setVisible(True)

    @staticmethod
    def _build_day_column() -> tuple[QVBoxLayout, dict[str, QLabel]]:
        column_layout = QVBoxLayout()
        column_layout.setSpacing(2)

        date_label = ElidingLabel("--")
        date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        date_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        weekday_label = QLabel("--")
        weekday_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weekday_label.setStyleSheet("color: #cccccc; font-size: 10px; font-weight: bold;")

        icon_label = QLabel("🌡️")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 18px;")

        temp_label = ElidingLabel("--/--")
        temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: bold;")
        temp_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        for widget in (date_label, weekday_label, icon_label, temp_label):
            column_layout.addWidget(widget)

        return column_layout, {
            "date": date_label,
            "weekday": weekday_label,
            "icon": icon_label,
            "temp": temp_label,
        }

    def _refresh(self) -> None:
        location = self._config.get("location")
        if not location:
            self._update_label.setText("未配置城市")
            return
        if self._thread is not None and self._thread.isRunning():
            return  # 上一次还没完成，跳过这次，避免并发请求

        self._thread = _WeatherFetchThread(location, self)
        self._thread.fetched.connect(self._on_fetched)
        self._thread.start()

    def _on_fetched(self, now: Optional[WeatherInfo], forecast: Optional[list[DayForecast]]) -> None:
        if forecast is None:
            return  # 静默失败，保留上一次展示的数据

        today = date.today()
        for column, day in zip(self._day_columns, forecast):
            day_date = date.fromisoformat(day.fx_date)
            column["date"].setText(day_date.strftime("%m/%d"))
            column["weekday"].setText("今天" if day_date == today else WEEKDAY_LABELS[day_date.weekday()])
            column["icon"].setText(weather_emoji(day.icon_code))
            column["temp"].setText(f"{day.temp_max}°/{day.temp_min}°")

        highs = [float(day.temp_max) for day in forecast]
        lows = [float(day.temp_min) for day in forecast]
        self._chart.set_data(highs, lows)

        self._last_update = datetime.now()
        self._update_relative_time_label()

    def _update_relative_time_label(self) -> None:
        if self._last_update is None:
            return
        seconds = (datetime.now() - self._last_update).total_seconds()
        if seconds < 60:
            text = "刚刚更新"
        elif seconds < 3600:
            text = f"{int(seconds // 60)} 分钟前"
        else:
            text = f"{int(seconds // 3600)} 小时前"
        self._update_label.setText(text)
