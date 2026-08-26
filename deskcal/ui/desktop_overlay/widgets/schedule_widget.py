"""桌面左栏紧凑课表组件。"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QDialog, QMenu, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from deskcal.core.schedule_storage import ScheduleStore
from deskcal.ui.schedule.schedule_grid import ScheduleGrid
from deskcal.ui.schedule.schedule_settings import ScheduleSettingsDialog
from deskcal.ui.schedule.schedule_window import ScheduleWindow


def default_schedule_config() -> dict:
    return {
        "show_weekends": False,
        "time_format": "12h",
        "notifications_enabled": False,
        "reminder_minutes": 20,
    }


class ScheduleWidget(QWidget):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QToolButton { background-color: rgba(255, 255, 255, 30); color: #ffffff; "
            "border: none; border-radius: 4px; padding: 5px 8px; text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 60); }"
            "QToolButton::menu-indicator { image: none; }"
            "QMenu { background-color: #242424; color: #f2f2f2; border: 1px solid #444444; padding: 4px; }"
            "QMenu::item { padding: 6px 20px 6px 8px; }"
            "QMenu::item:selected { background-color: #3b3b3b; }"
        )
        self._config = {**default_schedule_config(), **config}
        self._store = ScheduleStore()
        self._store.load()
        self._window: Optional[ScheduleWindow] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._term_button = QToolButton()
        self._term_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._term_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._menu = QMenu(self)
        self._menu.aboutToShow.connect(self._rebuild_menu)
        self._term_button.setMenu(self._menu)
        layout.addWidget(self._term_button)

        self._grid = ScheduleGrid(
            compact=True,
            show_weekends=self._config["show_weekends"],
            use_24_hour=self._config["time_format"] == "24h",
        )
        self._grid.courseClicked.connect(self._open_schedule_for_course)
        self._grid.emptyClicked.connect(self._open_schedule)
        layout.addWidget(self._grid)

        self._refresh()

    def _active_term(self):
        return self._store.get_active_term()

    def _refresh(self) -> None:
        term = self._active_term()
        self._term_button.setText(f"{term.name}  ▾" if term else "设置课表  ▾")
        self._grid.set_term(term)

    def _rebuild_menu(self) -> None:
        self._menu.clear()
        terms = sorted(self._store.terms.values(), key=lambda term: (term.archived, term.start_date))
        for term in terms:
            label = f"{term.name} · 已归档" if term.archived else term.name
            action = self._menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(term.id == self._store.active_term_id)
            action.triggered.connect(lambda _checked=False, term_id=term.id: self._select_term(term_id))
        if terms:
            self._menu.addSeparator()
        manage = self._menu.addAction("新增或管理学期…")
        manage.triggered.connect(self._open_settings)

    def _select_term(self, term_id: str) -> None:
        self._store.set_active_term(term_id)
        self._store.save()
        self._refresh()

    def _open_settings(self) -> None:
        dialog = ScheduleSettingsDialog(self._config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._config = dialog.result_config()
        self._persist_config()
        self._store.load()
        self._grid.set_show_weekends(self._config["show_weekends"])
        self._grid.set_use_24_hour(self._config["time_format"] == "24h")
        self._refresh()

    def _persist_config(self) -> None:
        # 延迟导入避免 registry 在注册 ScheduleWidget 时产生循环依赖。
        from deskcal.ui.desktop_overlay.widgets.registry import WidgetConfigStore

        widget_store = WidgetConfigStore()
        widget_store.load()
        for index, item in enumerate(widget_store.items):
            if item.type_id == "schedule":
                widget_store.update_config(index, dict(self._config))
                widget_store.save()
                return

    def _open_schedule_for_course(self, course_id: str) -> None:
        self._open_schedule(course_id)

    def _open_schedule(self, course_id: Optional[str] = None) -> None:
        if self._window is None:
            self._window = ScheduleWindow(self._config, selected_course_id=course_id)
            self._window.dataChanged.connect(self._reload_data)
            self._window.configChanged.connect(self._on_config_changed)
            self._window.destroyed.connect(lambda: setattr(self, "_window", None))
        elif course_id:
            self._window._select_course(course_id)
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _reload_data(self) -> None:
        self._store.load()
        self._refresh()

    def _on_config_changed(self, config: dict) -> None:
        self._config = dict(config)
        self._persist_config()
        self._grid.set_show_weekends(self._config.get("show_weekends", False))
        self._grid.set_use_24_hour(self._config.get("time_format", "12h") == "24h")
