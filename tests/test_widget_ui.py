import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

from deskcal.ui.config_panel.config_window import WidgetsTab
from deskcal.core.storage import CALENDAR_INTERACTION_CLICK, CALENDAR_INTERACTION_SCROLL, TaskStore
from deskcal.ui.desktop_overlay.calendar_grid import (
    CalendarGrid,
    ClickCalendarView,
    DayCellWidget,
    ScrollCalendarView,
    ScrollMonthSection,
    shifted_month,
)
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


def test_calendar_mode_setting_is_separate_and_notifies_immediately(app, tmp_path):
    store = WidgetConfigStore(file_path=tmp_path / "widgets.json")
    store.load()
    changed = []
    tab = WidgetsTab(
        store,
        lambda: None,
        CALENDAR_INTERACTION_SCROLL,
        changed.append,
    )

    assert tab._scroll_mode_button.isChecked()
    assert not tab._click_mode_button.isChecked()

    tab._click_mode_button.click()

    assert changed == [CALENDAR_INTERACTION_CLICK]
    assert tab._click_mode_button.isChecked()


def test_calendar_scroll_sensitivity_setting_notifies_immediately(app, tmp_path):
    store = WidgetConfigStore(file_path=tmp_path / "widgets.json")
    store.load()
    changed = []
    tab = WidgetsTab(
        store,
        lambda: None,
        CALENDAR_INTERACTION_SCROLL,
        lambda _mode: None,
        70,
        changed.append,
    )

    tab._scroll_sensitivity_slider.setValue(45)

    assert changed == [45]
    assert tab._scroll_sensitivity_value.text() == "45%"


def test_scroll_month_section_contains_only_its_own_dates(app, tmp_path):
    section = ScrollMonthSection(
        2026,
        10,
        TaskStore(file_path=tmp_path / "tasks.json"),
        100,
        100,
        lambda _day: None,
        lambda _task: None,
        lambda: None,
        lambda _event: None,
    )

    assert [cell._day for cell in section._day_cells] == [date(2026, 10, day) for day in range(1, 32)]


def test_calendar_grid_switches_without_replacing_click_mode(app, tmp_path):
    calendar = CalendarGrid(TaskStore(file_path=tmp_path / "tasks.json"))
    click_view = calendar._click_view

    calendar.set_interaction_mode(CALENDAR_INTERACTION_SCROLL)
    assert calendar.interaction_mode == CALENDAR_INTERACTION_SCROLL
    assert calendar._stack.currentWidget() is calendar._scroll_view

    calendar.set_interaction_mode(CALENDAR_INTERACTION_CLICK)
    assert calendar._stack.currentWidget() is click_view


def test_scroll_month_offsets_cross_year_boundaries():
    assert shifted_month(2026, 1, -1) == (2025, 12)
    assert shifted_month(2026, 12, 1) == (2027, 1)


def test_scroll_calendar_row_height_matches_click_calendar(app, tmp_path):
    store = TaskStore(file_path=tmp_path / "tasks.json")
    click_view = ClickCalendarView(store)
    scroll_view = ScrollCalendarView(store)
    for view in (click_view, scroll_view):
        view.resize(1000, 900)
        view.show()
    for _ in range(10):
        app.processEvents()
    scroll_view._apply_row_height_from_viewport()

    click_row_height = click_view._day_cells[0].height()

    assert abs(scroll_view._row_height - click_row_height) <= 1
    assert all(cell.height() == scroll_view._row_height for cell in scroll_view._sections[0]._day_cells)


def test_scroll_calendar_keeps_constant_spacing_when_prepending(app, tmp_path):
    scroll_view = ScrollCalendarView(TaskStore(file_path=tmp_path / "tasks.json"))
    scroll_view.resize(1000, 900)
    scroll_view.show()
    for _ in range(10):
        app.processEvents()
    scroll_view.ensure_initial_position()
    old_first = scroll_view._sections[0]

    scroll_view._scroll_area.verticalScrollBar().setValue(0)
    scroll_view._start_prefetch("before")
    for _ in range(20):
        app.processEvents()

    spacing = scroll_view._content_layout.spacing()
    gaps = [
        current.y() - (previous.y() + previous.height())
        for previous, current in zip(scroll_view._sections, scroll_view._sections[1:])
    ]
    assert set(gaps) == {spacing}
    assert scroll_view._scroll_area.verticalScrollBar().value() == old_first.y()


def test_scroll_month_height_does_not_clip_last_row_border(app, tmp_path):
    scroll_view = ScrollCalendarView(TaskStore(file_path=tmp_path / "tasks.json"))
    scroll_view.resize(1000, 900)
    scroll_view.show()
    for _ in range(10):
        app.processEvents()
    scroll_view._apply_row_height_from_viewport()
    scroll_view._sync_content_height()

    assert all(section.height() >= section._layout.sizeHint().height() for section in scroll_view._sections)


def test_scroll_sensitivity_scales_wheel_distance(app, tmp_path):
    class WheelEvent:
        def __init__(self):
            self.accepted = False

        def pixelDelta(self):
            return QPoint(0, -100)

        def angleDelta(self):
            return QPoint()

        def accept(self):
            self.accepted = True

    scroll_view = ScrollCalendarView(TaskStore(file_path=tmp_path / "tasks.json"))
    scroll_view.resize(1000, 900)
    scroll_view.show()
    for _ in range(10):
        app.processEvents()
    bar = scroll_view._scroll_area.verticalScrollBar()
    bar.setValue(500)
    scroll_view.set_scroll_sensitivity(50)
    event = WheelEvent()

    scroll_view._scroll_by_wheel(event)

    assert bar.value() == 550
    assert event.accepted


def test_wheel_over_inner_task_area_always_scrolls_outer_calendar(app, tmp_path):
    scroll_view = ScrollCalendarView(TaskStore(file_path=tmp_path / "tasks.json"))
    scroll_view.resize(1000, 900)
    scroll_view.show()
    for _ in range(10):
        app.processEvents()
    scroll_view.ensure_initial_position()
    bar = scroll_view._scroll_area.verticalScrollBar()
    before = bar.value()
    target = scroll_view._sections[2]._day_cells[0].findChild(QScrollArea).viewport()
    local_position = QPointF(2, 2)
    event = QWheelEvent(
        local_position,
        QPointF(target.mapToGlobal(QPoint(2, 2))),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    QApplication.sendEvent(target, event)

    assert bar.value() > before
    assert event.isAccepted()


def test_scroll_calendar_resizes_in_place_and_keeps_centered_month(app, tmp_path):
    scroll_view = ScrollCalendarView(TaskStore(file_path=tmp_path / "tasks.json"))
    scroll_view.resize(1000, 700)
    scroll_view.show()
    for _ in range(10):
        app.processEvents()
    scroll_view.ensure_initial_position()
    target = scroll_view._sections[3]
    scroll_view._center_section(target)
    original_cell_ids = [id(cell) for section in scroll_view._sections for cell in section._day_cells]

    for height in (820, 560, 900):
        scroll_view.resize(1200, height)
        app.processEvents()
        assert scroll_view._centered_section().key == target.key
        assert all(section.height() == section._layout.sizeHint().height() for section in scroll_view._sections)

    resized_cell_ids = [id(cell) for section in scroll_view._sections for cell in section._day_cells]
    assert resized_cell_ids == original_cell_ids


def test_scroll_calendar_returns_to_current_month_after_inactivity(app, tmp_path):
    class WheelEvent:
        def pixelDelta(self):
            return QPoint(0, -100)

        def angleDelta(self):
            return QPoint()

        def accept(self):
            pass

    scroll_view = ScrollCalendarView(TaskStore(file_path=tmp_path / "tasks.json"))
    scroll_view.resize(1000, 900)
    scroll_view.show()
    for _ in range(10):
        app.processEvents()
    scroll_view.ensure_initial_position()
    scroll_view._center_section(scroll_view._sections[-2])

    assert scroll_view._return_to_current_timer.interval() == 15_000
    scroll_view._return_to_current_timer.setInterval(10)
    scroll_view._scroll_by_wheel(WheelEvent())

    assert scroll_view._return_to_current_timer.isActive()
    QTest.qWait(300)

    today = date.today()
    assert scroll_view._centered_section().key == (today.year, today.month)
