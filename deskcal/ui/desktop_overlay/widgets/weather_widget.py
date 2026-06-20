"""天气组件：单例型，固定高度。网络请求放在 QThread 里跑，避免阻塞 UI；
失败时静默保留上一次显示的数据，不弹错误。
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from deskcal.services.weather_service import WeatherInfo, get_current_weather

ROW_HEIGHT = 60
REFRESH_INTERVAL_MS = 30 * 60 * 1000  # 30 分钟


def default_weather_config() -> dict:
    return {"location": ""}


class _WeatherFetchThread(QThread):
    fetched = pyqtSignal(object)  # Optional[WeatherInfo]

    def __init__(self, location: str, parent=None):
        super().__init__(parent)
        self._location = location

    def run(self) -> None:
        result = get_current_weather(self._location)
        self.fetched.emit(result)


class WeatherWidget(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._thread: Optional[_WeatherFetchThread] = None

        self.setFixedHeight(ROW_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._info_label = QLabel("天气加载中…")
        self._info_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self._info_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_INTERVAL_MS)
        self._refresh()

    def _refresh(self) -> None:
        location = self._config.get("location")
        if not location:
            self._info_label.setText("未配置城市")
            return
        if self._thread is not None and self._thread.isRunning():
            return  # 上一次还没完成，跳过这次，避免并发请求

        self._thread = _WeatherFetchThread(location, self)
        self._thread.fetched.connect(self._on_fetched)
        self._thread.start()

    def _on_fetched(self, info: Optional[WeatherInfo]) -> None:
        if info is None:
            return  # 静默失败，保留上一次展示的数据
        self._info_label.setText(f"{info.text} {info.temperature_c}℃")
