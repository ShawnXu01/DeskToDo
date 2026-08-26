"""定时检查当前课表，并通过回调发送 Windows 本机通知。"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QTimer

from deskcal.core.schedule_reminders import find_due_course_reminders
from deskcal.core.schedule_storage import ScheduleStore
from deskcal.core.storage import atomic_write_json, get_data_dir
from deskcal.ui.desktop_overlay.widgets.registry import WidgetConfigStore
from deskcal.ui.desktop_overlay.widgets.schedule_widget import default_schedule_config

REMINDER_STATE_FILE_NAME = "schedule_reminder_state.json"
CHECK_INTERVAL_MS = 30_000


class ScheduleReminderService(QObject):
    def __init__(
        self,
        notify: Callable[[str, str], None],
        *,
        schedule_store: Optional[ScheduleStore] = None,
        widget_store: Optional[WidgetConfigStore] = None,
        state_path: Optional[Path] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._notify = notify
        self._schedule_store = schedule_store or ScheduleStore()
        self._widget_store = widget_store or WidgetConfigStore()
        self._state_path = state_path or get_data_dir() / REMINDER_STATE_FILE_NAME
        self._state_date: Optional[date] = None
        self._sent_keys: set[str] = set()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_now)

    def start(self) -> None:
        self.check_now()
        self._timer.start(CHECK_INTERVAL_MS)

    def check_now(self, now: Optional[datetime] = None) -> None:
        current = now or datetime.now()
        config = self._load_config()
        if not config["notifications_enabled"]:
            return

        self._ensure_state_loaded(current.date())
        try:
            self._schedule_store.load()
        except (OSError, ValueError, json.JSONDecodeError):
            return

        term = self._schedule_store.get_active_term(current.date())
        reminders = find_due_course_reminders(term, current, config["reminder_minutes"])
        for reminder in reminders:
            if reminder.key in self._sent_keys:
                continue
            self._notify(reminder.title, reminder.message)
            self._sent_keys.add(reminder.key)
            self._save_state(current.date())

    def _load_config(self) -> dict:
        config = default_schedule_config()
        try:
            self._widget_store.load()
        except (OSError, ValueError, json.JSONDecodeError):
            return config
        schedule = next((item for item in self._widget_store.items if item.type_id == "schedule"), None)
        if schedule is not None:
            config.update(schedule.config)
        try:
            config["reminder_minutes"] = max(1, min(180, int(config["reminder_minutes"])))
        except (TypeError, ValueError):
            config["reminder_minutes"] = 20
        config["notifications_enabled"] = config.get("notifications_enabled") is True
        return config

    def _ensure_state_loaded(self, today: date) -> None:
        if self._state_date == today:
            return
        self._state_date = today
        self._sent_keys = set()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return
        if raw.get("date") == today.isoformat() and isinstance(raw.get("sent_keys"), list):
            self._sent_keys = {key for key in raw["sent_keys"] if isinstance(key, str)}

    def _save_state(self, today: date) -> None:
        atomic_write_json(
            self._state_path,
            {"date": today.isoformat(), "sent_keys": sorted(self._sent_keys)},
        )
