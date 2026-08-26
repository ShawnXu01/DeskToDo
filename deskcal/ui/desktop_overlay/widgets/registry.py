"""组件注册表：静态类型清单 + 用户启用状态/顺序/各自配置的持久化。

桌面层和配置面板共享这一份数据：新增一种组件类型只需要在 WIDGET_DEFINITIONS 里注册，
两端不需要分别改代码。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtWidgets import QWidget

from deskcal.core.storage import atomic_write_json, get_data_dir
from deskcal.ui.desktop_overlay.widgets.clock_widget import ClockWidget, default_clock_config
from deskcal.ui.desktop_overlay.widgets.countdown_widget import CountdownWidget, default_countdown_config
from deskcal.ui.desktop_overlay.widgets.progress_widget import ProgressWidget, default_progress_config
from deskcal.ui.desktop_overlay.widgets.schedule_widget import ScheduleWidget, default_schedule_config
from deskcal.ui.desktop_overlay.widgets.weather_widget import WeatherWidget, default_weather_config

WIDGETS_FILE_NAME = "widgets.json"


@dataclass
class WidgetDefinition:
    type_id: str
    display_name: str
    widget_class: Optional[Callable[..., QWidget]]  # 特殊组件可由桌面层接管构造
    default_config: Callable[[], dict]
    configurable: bool  # False 表示没有可设置项（如时钟），配置面板里"设置"按钮应禁用


WIDGET_DEFINITIONS: dict[str, WidgetDefinition] = {
    "clock": WidgetDefinition("clock", "时钟", ClockWidget, default_clock_config, configurable=False),
    "countdown": WidgetDefinition("countdown", "倒计时", CountdownWidget, default_countdown_config, configurable=True),
    "weather": WidgetDefinition("weather", "天气", WeatherWidget, default_weather_config, configurable=True),
    "floating_todo": WidgetDefinition("floating_todo", "无日期待办", None, dict, configurable=False),
    "schedule": WidgetDefinition("schedule", "课表", ScheduleWidget, default_schedule_config, configurable=True),
    "progress": WidgetDefinition("progress", "进度条", ProgressWidget, default_progress_config, configurable=True),
}

DEFAULT_ORDER = ["clock", "weather", "floating_todo", "countdown", "progress", "schedule"]


@dataclass
class WidgetInstanceConfig:
    type_id: str
    enabled: bool = True
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type_id": self.type_id, "enabled": self.enabled, "config": self.config}

    @classmethod
    def from_dict(cls, data: dict) -> "WidgetInstanceConfig":
        return cls(type_id=data["type_id"], enabled=data.get("enabled", True), config=data.get("config", {}))


def get_widgets_file() -> Path:
    return get_data_dir() / WIDGETS_FILE_NAME


class WidgetConfigStore:
    """持久化用户的组件启用状态、顺序、各自配置。"""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or get_widgets_file()
        self.items: list[WidgetInstanceConfig] = []

    def load(self) -> None:
        if not self.file_path.exists():
            self.items = [
                WidgetInstanceConfig(type_id=type_id, config=WIDGET_DEFINITIONS[type_id].default_config())
                for type_id in DEFAULT_ORDER
            ]
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.items = [WidgetInstanceConfig.from_dict(item) for item in raw.get("widgets", [])]
        existing_type_ids = {item.type_id for item in self.items}
        for type_id in DEFAULT_ORDER:
            if type_id not in existing_type_ids:
                new_item = WidgetInstanceConfig(
                    type_id=type_id,
                    config=WIDGET_DEFINITIONS[type_id].default_config(),
                )
                if type_id == "floating_todo":
                    weather_index = next(
                        (index for index, item in enumerate(self.items) if item.type_id == "weather"),
                        None,
                    )
                    if weather_index is not None:
                        self.items.insert(weather_index + 1, new_item)
                        continue
                self.items.append(new_item)

    def save(self) -> None:
        payload = {"widgets": [item.to_dict() for item in self.items]}
        atomic_write_json(self.file_path, payload)

    def enabled_items(self) -> list[WidgetInstanceConfig]:
        return [item for item in self.items if item.enabled]

    def move_up(self, index: int) -> None:
        if index <= 0:
            return
        self.items[index - 1], self.items[index] = self.items[index], self.items[index - 1]

    def move_down(self, index: int) -> None:
        if index >= len(self.items) - 1:
            return
        self.items[index + 1], self.items[index] = self.items[index], self.items[index + 1]

    def reorder(self, type_ids: list[str]) -> None:
        """按完整的组件类型列表重排；列表缺失或重复时拒绝写入。"""
        if len(type_ids) != len(self.items) or set(type_ids) != {item.type_id for item in self.items}:
            raise ValueError("组件顺序必须完整且不能包含重复项")
        items_by_type = {item.type_id: item for item in self.items}
        self.items = [items_by_type[type_id] for type_id in type_ids]

    def set_enabled(self, index: int, enabled: bool) -> None:
        self.items[index].enabled = enabled

    def update_config(self, index: int, config: dict) -> None:
        self.items[index].config = config
