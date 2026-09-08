import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from deskcal.ui.config_panel.config_window import WidgetsTab
from deskcal.ui.desktop_overlay.calendar_grid import DayCellWidget
from deskcal.ui.desktop_overlay.overlay_window import OverlayWindow
from deskcal.ui.desktop_overlay.task_chip import TaskChipWidget
from deskcal.ui.desktop_overlay.widgets.registry import WidgetConfigStore


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_today_cell_uses_red_border_without_changing_border_width(app):
    today_cell = DayCellWidget(date(2026, 9, 8), True, True, 100, lambda _day: None, lambda _day: None)
    regular_cell = DayCellWidget(date(2026, 9, 9), True, False, 100, lambda _day: None, lambda _day: None)

    assert "QFrame#dayCell { border: 2px solid #e53935; }" in today_cell.styleSheet()
    assert "QFrame#dayCell { border: 2px solid rgba(255, 255, 255, 160); }" in regular_cell.styleSheet()


def test_registered_widget_shortcut_opens_its_settings(app):
    opened = []

    class OverlayStub:
        def open_config_panel(self, type_id):
            opened.append(type_id)

    widget = QWidget()
    layout = QVBoxLayout(widget)
    child = QLabel("天气内容")
    layout.addWidget(child)
    OverlayWindow._enable_widget_settings(OverlayStub(), widget, "weather")
    widget.resize(200, 100)
    widget.show()
    app.processEvents()

    assert widget.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    position = QPoint(4, 4)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        position,
        child.mapToGlobal(position),
    )
    QApplication.sendEvent(child, event)
    assert opened == ["weather"]


def test_task_chip_keeps_its_existing_right_click_edit(app):
    opened = []

    class OverlayStub:
        def open_config_panel(self, type_id):
            opened.append(type_id)

    widget = QWidget()
    layout = QVBoxLayout(widget)
    task_chip = TaskChipWidget(name="任务", color="#e53935", completed=False)
    layout.addWidget(task_chip)
    OverlayWindow._enable_widget_settings(OverlayStub(), widget, "floating_todo")
    edits = []
    task_chip.editRequested.connect(lambda: edits.append(True))
    widget.resize(200, 100)
    widget.show()
    app.processEvents()

    position = QPoint(2, 2)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        position,
        task_chip._name_label.mapToGlobal(position),
    )
    QApplication.sendEvent(task_chip._name_label, event)

    assert edits == [True]
    assert opened == []


def test_widget_settings_focuses_target_and_opens_configurable_dialog(app, tmp_path):
    store = WidgetConfigStore(file_path=tmp_path / "widgets.json")
    store.load()
    tab = WidgetsTab(store, lambda: None)
    opened = []
    tab._open_settings = lambda index: opened.append(store.items[index].type_id)

    tab.open_widget_settings("weather")

    assert tab._list.currentItem().data(Qt.ItemDataRole.UserRole) == "weather"
    assert opened == ["weather"]


def test_widget_without_extra_options_is_still_focused(app, tmp_path):
    store = WidgetConfigStore(file_path=tmp_path / "widgets.json")
    store.load()
    tab = WidgetsTab(store, lambda: None)
    opened = []
    tab._open_settings = lambda index: opened.append(store.items[index].type_id)

    tab.open_widget_settings("clock")

    assert tab._list.currentItem().data(Qt.ItemDataRole.UserRole) == "clock"
    assert opened == []
