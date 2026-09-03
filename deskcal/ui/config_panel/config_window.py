"""配置面板：同程序的第二个窗口，有边框。左侧导航 + 右侧内容，各 tab 见下方对应类的 docstring。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtCore import QPoint, QSize, QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.storage import list_window_profiles, load_appearance, save_appearance
from deskcal.services import autostart
from deskcal.services.lunar_holiday import get_holidays_file
from deskcal.services.sync_manager import SyncManager
from deskcal.ui.desktop_overlay.widgets.registry import WIDGET_DEFINITIONS, WidgetConfigStore
from deskcal.ui.dialogs.date_field import DateField
from deskcal.ui.schedule.schedule_settings import ScheduleSettingsDialog
from deskcal.ui.style_utils import ElidingLabel
from deskcal.utils import crypto
from deskcal.utils.icons import app_icon
from deskcal.utils.monitor import compute_monitor_signature

CONFIG_WINDOW_QSS = (
    """
QWidget {
    color: #f4f4f4;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
QWidget#settingsWindow, QDialog { background-color: #191919; }
QFrame#settingsSidebar { background-color: #202020; border-right: 1px solid #363636; }
QFrame#settingsContent { background-color: #191919; }
QLabel { background: transparent; }
QLabel#settingsBrand { color: #ffffff; font-size: 20px; font-weight: 700; }
QLabel#settingsCaption, QLabel#settingsSubtitle { color: #a9a9a9; }
QLabel#settingsTitle { color: #ffffff; font-size: 20px; font-weight: 700; }
QFrame#settingsDivider { background-color: #333333; border: none; }
QPushButton {
    min-height: 34px;
    background-color: #2b2b2b;
    color: #f4f4f4;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 0 14px;
}
QPushButton:hover { background-color: #363636; border-color: #5a5a5a; }
QPushButton:pressed { background-color: #242424; }
QPushButton:checked { background-color: #123d70; border-color: #2865a8; }
QPushButton:disabled { color: #707070; background-color: #222222; border-color: #303030; }
QLineEdit, QTimeEdit {
    min-height: 34px;
    background-color: #242424;
    color: #f4f4f4;
    border: 1px solid #454545;
    border-radius: 6px;
    padding: 0 10px;
}
QListWidget {
    background-color: #222222;
    color: #f4f4f4;
    border: 1px solid #383838;
    border-radius: 8px;
    outline: none;
}
QListWidget::item { min-height: 38px; padding: 0 10px; }
QListWidget::item:selected { background-color: #123d70; color: #ffffff; }
QListWidget#settingsNav { background: transparent; border: none; border-radius: 0; }
QListWidget#settingsNav::item {
    min-height: 48px;
    padding: 0 14px;
    margin: 2px 0;
    border-radius: 8px;
    color: #cccccc;
}
QListWidget#settingsNav::item:hover { background-color: #2b2b2b; color: #ffffff; }
QListWidget#settingsNav::item:selected { background-color: #123d70; color: #ffffff; }
QFrame#widgetSettingsRow {
    min-height: 68px;
    background-color: #222222;
    border: 1px solid #363636;
    border-radius: 8px;
}
QListWidget#widgetSettingsList { background: transparent; border: none; border-radius: 0; }
QListWidget#widgetSettingsList::item {
    min-height: 76px;
    padding: 0;
    margin: 0 0 8px 0;
    background: transparent;
}
QListWidget#widgetSettingsList::item:selected { background: transparent; }
QLabel#dragHandle { color: #777777; font-size: 18px; padding: 0 4px; }
QLabel#widgetDescription { color: #9f9f9f; font-size: 11px; }
QFrame#widgetPreview {
    min-width: 172px;
    max-width: 172px;
    min-height: 42px;
    background-color: #181818;
    border: 1px solid #343434;
    border-radius: 6px;
}
QLabel#previewCaption { color: #888888; font-size: 10px; }
QLabel#previewValue { color: #ededed; font-size: 12px; font-weight: 600; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QSlider::groove:horizontal { height: 5px; background: #3a3a3a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #2865a8; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 18px;
    margin: -7px 0;
    background: #f4f4f4;
    border: 2px solid #2865a8;
    border-radius: 9px;
}
"""
)


def _build_construction_notice() -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setSpacing(4)

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedWidth(160)
    line.setStyleSheet("background-color: rgba(255, 255, 255, 60); border: none;")
    layout.addWidget(line, alignment=Qt.AlignmentFlag.AlignCenter)

    notice = QLabel("施工中...\nContact: XCH_ShawnXu")
    notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
    notice.setStyleSheet("color: rgba(255, 255, 255, 120); font-size: 11px;")
    layout.addWidget(notice)

    return container


def _add_checkable_row(list_widget: QListWidget, text: str) -> QCheckBox:
    """倒计时/进度条设置列表共用：每行前面加一个复选框，方便批量选中后删除。"""
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(4, 2, 4, 2)
    checkbox = QCheckBox()
    label = QLabel(text)
    row_layout.addWidget(checkbox)
    row_layout.addWidget(label, 1)

    item = QListWidgetItem()
    list_widget.addItem(item)
    list_widget.setItemWidget(item, row)
    return checkbox


class WeatherSettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("天气设置")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(CONFIG_WINDOW_QSS)
        self._config = dict(config)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "城市定位，填下面两种格式之一：\n"
            "1. 经度,纬度，比如 120.68,30.51\n"
            "2. 和风天气 LocationID（数字编码），获取方式：打开 qweather.com 搜索你的城市，"
            "进入城市天气页面，地址栏网址末尾的数字（如 .../haining-101210303.html 里的 101210303）就是 LocationID\n\n"
            "城市名称会在保存后自动通过和风天气接口查出来显示在天气组件上，不需要自己填。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._location_edit = QLineEdit(self._config.get("location", ""))
        self._location_edit.setPlaceholderText("例：120.68,30.51 或 101210303")
        layout.addWidget(self._location_edit)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

    def result_config(self) -> dict:
        return {"location": self._location_edit.text().strip()}


class CountdownSettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("倒计时设置")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(CONFIG_WINDOW_QSS)
        self._items: list[dict] = list(config.get("items", []))
        self._checkboxes: list[QCheckBox] = []

        layout = QVBoxLayout(self)
        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

        add_row = QHBoxLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("标题，如 AAAI 截稿")
        self._deadline_date_edit = DateField()
        self._deadline_time_edit = QTimeEdit(datetime.now().time())
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_item)
        add_row.addWidget(self._title_edit)
        add_row.addWidget(self._deadline_date_edit)
        add_row.addWidget(self._deadline_time_edit)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self._remove_selected)
        layout.addWidget(remove_btn)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list_widget.clear()
        self._checkboxes = [
            _add_checkable_row(self._list_widget, f"{item['title']} — {item['deadline']}")
            for item in self._items
        ]

    def _add_item(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            return
        deadline_dt = datetime.combine(self._deadline_date_edit.date(), self._deadline_time_edit.time().toPyTime())
        deadline_iso = deadline_dt.isoformat()
        self._items.append({"title": title, "deadline": deadline_iso})
        self._title_edit.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        for index in sorted(
            (i for i, cb in enumerate(self._checkboxes) if cb.isChecked()), reverse=True
        ):
            del self._items[index]
        self._refresh_list()

    def result_config(self) -> dict:
        return {"items": self._items}


class ProgressSettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("进度条设置")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(CONFIG_WINDOW_QSS)
        self._items: list[dict] = list(config.get("items", []))
        self._checkboxes: list[QCheckBox] = []

        layout = QVBoxLayout(self)
        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

        add_row = QHBoxLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("标题，如 本学期进度")
        self._start_edit = DateField()
        self._end_edit = DateField()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_item)
        add_row.addWidget(self._title_edit)
        add_row.addWidget(self._start_edit)
        add_row.addWidget(self._end_edit)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self._remove_selected)
        layout.addWidget(remove_btn)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list_widget.clear()
        self._checkboxes = [
            _add_checkable_row(self._list_widget, f"{item['title']} — {item['start']} ~ {item['end']}")
            for item in self._items
        ]

    def _add_item(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            return
        start_iso = self._start_edit.date().isoformat()
        end_iso = self._end_edit.date().isoformat()
        self._items.append({"title": title, "start": start_iso, "end": end_iso})
        self._title_edit.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        for index in sorted(
            (i for i, cb in enumerate(self._checkboxes) if cb.isChecked()), reverse=True
        ):
            del self._items[index]
        self._refresh_list()

    def result_config(self) -> dict:
        return {"items": self._items}


SETTINGS_DIALOGS = {
    "weather": WeatherSettingsDialog,
    "countdown": CountdownSettingsDialog,
    "progress": ProgressSettingsDialog,
    "schedule": ScheduleSettingsDialog,
}


_WIDGET_DESCRIPTIONS = {
    "clock": "当前时间，每秒自动更新",
    "weather": "当前天气与未来几日预报",
    "floating_todo": "集中显示没有日期的待办",
    "countdown": "跟踪临近事件的剩余时间",
    "progress": "查看长期目标的完成进度",
    "schedule": "查看当前学期的周课表",
}


class _DragHandle(QLabel):
    def __init__(self, begin_drag: Callable[[], None], parent=None):
        super().__init__("⋮⋮", parent)
        self.setObjectName("dragHandle")
        self.setToolTip("按住并拖动以调整桌面顺序")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._begin_drag = begin_drag
        self._press_position: Optional[QPoint] = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press_position is not None:
            distance = (event.position().toPoint() - self._press_position).manhattanLength()
            if distance >= QApplication.startDragDistance():
                self._press_position = None
                self._begin_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_position = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class _WidgetPreview(QFrame):
    def __init__(self, type_id: str, config: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("widgetPreview")
        self._type_id = type_id
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(0)
        caption = QLabel("实时预览")
        caption.setObjectName("previewCaption")
        self._value = ElidingLabel()
        self._value.setObjectName("previewValue")
        layout.addWidget(caption)
        layout.addWidget(self._value)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1_000 if type_id == "clock" else 60_000)
        self._refresh()

    def _refresh(self) -> None:
        if self._type_id == "clock":
            text = datetime.now().strftime("%H:%M:%S")
        elif self._type_id == "weather":
            text = "城市已配置" if self._config.get("location") else "尚未设置城市"
        elif self._type_id == "floating_todo":
            text = "无日期待办列表"
        elif self._type_id == "countdown":
            items = self._config.get("items", [])
            text = f"{len(items)} 个倒计时" if items else "暂无倒计时"
        elif self._type_id == "progress":
            items = self._config.get("items", [])
            text = f"{len(items)} 个长期目标" if items else "暂无长期目标"
        else:
            time_format = "24 小时" if self._config.get("time_format") == "24h" else "12 小时"
            weekends = "显示周末" if self._config.get("show_weekends") else "工作日课表"
            text = f"{time_format} · {weekends}"
        self._value.setText(text)


class WidgetsTab(QWidget):
    def __init__(self, store: WidgetConfigStore, on_changed: Callable[[], None], parent=None):
        super().__init__(parent)
        self._store = store
        self._on_changed = on_changed

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

        hint = QLabel("按住左侧拖动手柄调整顺序，桌面会立即同步更新。")
        hint.setObjectName("settingsSubtitle")
        self._layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setObjectName("widgetSettingsList")
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setDropIndicatorShown(True)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        self._layout.addWidget(self._list, 1)

        self.render()

    def render(self) -> None:
        self._list.clear()

        for index, instance in enumerate(self._store.items):
            definition = WIDGET_DEFINITIONS[instance.type_id]

            row = QFrame()
            row.setObjectName("widgetSettingsRow")
            row.setFixedHeight(68)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 7, 10, 7)
            row_layout.setSpacing(8)

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, instance.type_id)
            item.setSizeHint(QSize(0, 76))
            self._list.addItem(item)

            drag_handle = _DragHandle(lambda list_item=item: self._begin_drag(list_item))
            row_layout.addWidget(drag_handle)

            enabled_checkbox = QPushButton("已启用" if instance.enabled else "已关闭")
            enabled_checkbox.setMinimumWidth(74)
            enabled_checkbox.setCheckable(True)
            enabled_checkbox.setChecked(instance.enabled)
            enabled_checkbox.toggled.connect(lambda checked, i=index: self._toggle_enabled(i, checked))
            row_layout.addWidget(enabled_checkbox)

            text_column = QVBoxLayout()
            text_column.setSpacing(1)
            name_label = QLabel(definition.display_name)
            description = QLabel(_WIDGET_DESCRIPTIONS[instance.type_id])
            description.setObjectName("widgetDescription")
            text_column.addWidget(name_label)
            text_column.addWidget(description)
            row_layout.addLayout(text_column, 1)

            row_layout.addWidget(_WidgetPreview(instance.type_id, instance.config))

            settings_btn = QPushButton("设置")
            settings_btn.setEnabled(definition.configurable)
            settings_btn.clicked.connect(lambda _checked=False, i=index: self._open_settings(i))
            row_layout.addWidget(settings_btn)

            self._list.setItemWidget(item, row)

    def _begin_drag(self, item: QListWidgetItem) -> None:
        self._list.setCurrentItem(item)
        self._list.startDrag(Qt.DropAction.MoveAction)

    def _on_rows_moved(self, *_args) -> None:
        type_ids = [
            self._list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self._list.count())
        ]
        self._store.reorder(type_ids)
        self._store.save()
        self._on_changed()
        QTimer.singleShot(0, self.render)

    def _toggle_enabled(self, index: int, checked: bool) -> None:
        self._store.set_enabled(index, checked)
        self._store.save()
        self._on_changed()
        self.render()

    def _open_settings(self, index: int) -> None:
        instance = self._store.items[index]
        dialog_class = SETTINGS_DIALOGS.get(instance.type_id)
        if dialog_class is None:
            return
        dialog = dialog_class(instance.config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._store.update_config(index, dialog.result_config())
            self._store.save()
            self._on_changed()


class UISettingsTab(QWidget):
    """界面外观调整：日历悬浮窗背板透明度与启动行为。"""

    def __init__(
        self,
        current_panel_alpha: int,
        on_panel_alpha_changed: Callable[[int], None],
        parent=None,
    ):
        super().__init__(parent)
        self._on_panel_alpha_changed = on_panel_alpha_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(QLabel("日历悬浮窗背板透明度"))

        row = QHBoxLayout()
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(round(current_panel_alpha / 255 * 100))
        self._value_label = QLabel(f"{self._slider.value()}%")
        self._slider.valueChanged.connect(self._on_slider_changed)
        row.addWidget(self._slider, 1)
        row.addWidget(self._value_label)
        layout.addLayout(row)

        self._autostart_checkbox = QCheckBox("开机自动启动")
        self._autostart_checkbox.setChecked(load_appearance()["autostart_enabled"])
        self._autostart_checkbox.toggled.connect(self._on_autostart_toggled)
        layout.addWidget(self._autostart_checkbox)

        layout.addStretch(1)

    def _on_autostart_toggled(self, checked: bool) -> None:
        save_appearance(autostart_enabled=checked)
        if checked:
            autostart.enable_autostart()
        else:
            autostart.disable_autostart()

    def _on_slider_changed(self, percent: int) -> None:
        self._value_label.setText(f"{percent}%")
        alpha = round(percent / 100 * 255)
        self._on_panel_alpha_changed(alpha)


class HolidayInfoTab(QWidget):
    """法定节假日每年安排不同，需要用户自行下载当年数据导入；母亲节/父亲节等公式类特殊日期不需要导入，自动计算。"""

    def __init__(self, on_holidays_changed: Callable[[], None], parent=None):
        super().__init__(parent)
        self._on_holidays_changed = on_holidays_changed

        layout = QVBoxLayout(self)
        hint = QLabel(
            "法定节假日（春节、国庆节等）每年的具体安排由国务院每年发布，程序内置了发布时已知年份的"
            "默认数据；美国报税截止日等受年度公告影响的重要日期也使用同一份数据，但以后年份需要你自己更新。\n\n"
            "获取方式：搜索“国务院办公厅 关于 X 年部分节假日安排的通知”（新华社/中国政府网会发布），"
            "同时从对应政府官网核对美国年度日期，统一整理成如下格式的 JSON 文件（日期: 名称）：\n\n"
            '{\n  "2026-01-01": "元旦",\n  "2026-04-15": "美国报税截止日",\n  "2026-05-01": "劳动节"\n}\n\n'
            "整理好后点击下面的按钮选择该文件导入即可，日历会立即按新数据显示。\n"
            "（感恩节、黑色星期五等按公式计算的日期不受影响，不需要导入。）"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        import_btn = QPushButton("选择文件导入...")
        import_btn.clicked.connect(self._import_file)
        layout.addWidget(import_btn)

        self._status_label = QLabel(self._current_status_text())
        layout.addWidget(self._status_label)

        layout.addStretch(1)

    def _current_status_text(self) -> str:
        path = get_holidays_file()
        if not path.exists():
            return "当前未导入任何节假日数据"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return f"当前已导入 {len(data)} 条节假日数据"
        except (json.JSONDecodeError, OSError):
            return "当前节假日数据文件格式异常"

    def _import_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择节假日数据文件", "", "JSON 文件 (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("根节点必须是对象")
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "导入失败", f"文件格式不正确：{exc}")
            return

        with open(get_holidays_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._status_label.setText(self._current_status_text())
        self._on_holidays_changed()


class MonitorSettingsTab(QWidget):
    """显示不同显示器组合下分别记忆的悬浮窗位置，只读展示，不提供编辑。

    QTableWidget 在 Windows 原生主题下表头不听 QSS/item 前景色，白底白字看不见；
    干脆不用自带表头的表格控件，照搬 MiniCalendarPicker 那种自己拼 QLabel 网格的
    实心暗色块写法，颜色完全自己说了算。
    """

    COLUMNS = ["显示器签名", "X", "Y", "宽度", "高度", "左侧宽度", "上区比例"]
    COLUMN_STRETCH = [3, 1, 1, 1, 1, 1, 1]

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "DeskToDo 会按你当前接的显示器组合（比如单独用笔记本屏幕、还是外接了别的显示器）"
            "自动记住悬浮窗的位置、大小、左侧宽度和上下区域比例。换一套显示器组合时会自动套用对应记录；"
            "新组合第一次出现时还没有记录，会先用默认位置，你调整好之后会自动记下来，"
            "下次换回这套组合就会自动恢复。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._table_frame = QFrame()
        self._table_frame.setStyleSheet("QFrame { background-color: #202020; border-radius: 4px; }")
        self._grid = QGridLayout(self._table_frame)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(6)
        for col, stretch in enumerate(self.COLUMN_STRETCH):
            self._grid.setColumnStretch(col, stretch)
        layout.addWidget(self._table_frame)
        layout.addStretch(1)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_table)
        layout.addWidget(refresh_btn)

        self._refresh_table()

    def _refresh_table(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for col, name in enumerate(self.COLUMNS):
            self._grid.addWidget(self._make_cell(name, bold=True), 0, col)

        current_signature = compute_monitor_signature()
        profiles = list_window_profiles()
        for row, (signature, geometry) in enumerate(profiles.items(), start=1):
            label = f"{signature}（当前）" if signature == current_signature else signature
            values = [
                label,
                geometry.get("x"),
                geometry.get("y"),
                geometry.get("width"),
                geometry.get("height"),
                geometry.get("left_area_width", "旧版布局"),
                (
                    f"{geometry['left_top_ratio']:.0%}"
                    if isinstance(geometry.get("left_top_ratio"), (int, float))
                    else "旧版布局"
                ),
            ]
            for col, value in enumerate(values):
                self._grid.addWidget(self._make_cell(str(value)), row, col)

    @staticmethod
    def _make_cell(text: str, bold: bool = False) -> QLabel:
        label = ElidingLabel(text)
        weight = "bold" if bold else "normal"
        label.setStyleSheet(f"color: #ffffff; font-weight: {weight}; background: transparent;")
        return label


class SyncTab(QWidget):
    """Gist Token 填写 + 立即同步 + 状态显示。Token 改动需要重启 DeskToDo 才会生效，
    不在面板里动态重建同步线程，避免运行时热切换带来的复杂度。"""

    def __init__(self, sync_manager: Optional[SyncManager], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("GitHub Gist Token（保存后需重启 DeskToDo 才会生效）"))
        self._token_edit = QLineEdit(crypto.load_gist_token() or "")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._token_edit)

        save_btn = QPushButton("保存 Token")
        save_btn.clicked.connect(self._save_token)
        layout.addWidget(save_btn)

        gist_id_hint = QLabel(
            "Gist ID（高级选项，一般不用填）：同一账号下多台电脑只要填同一个 Token，"
            "会自动找到上一台电脑创建的那份数据并接上；只有当自动识别不到、或者你想强制指定"
            "连到某一份具体的 Gist 时才需要在这里手动填。保存后也需要重启 DeskToDo 才会生效。"
        )
        gist_id_hint.setWordWrap(True)
        layout.addWidget(gist_id_hint)
        gist_id_row = QHBoxLayout()
        self._gist_id_edit = QLineEdit(crypto.load_gist_id() or "")
        gist_id_row.addWidget(self._gist_id_edit, 1)
        copy_gist_id_btn = QPushButton("复制")
        copy_gist_id_btn.clicked.connect(self._copy_gist_id)
        gist_id_row.addWidget(copy_gist_id_btn)
        clear_gist_id_btn = QPushButton("清除")
        clear_gist_id_btn.clicked.connect(self._clear_gist_id)
        gist_id_row.addWidget(clear_gist_id_btn)
        layout.addLayout(gist_id_row)

        save_gist_id_btn = QPushButton("保存 Gist ID")
        save_gist_id_btn.clicked.connect(self._save_gist_id)
        layout.addWidget(save_gist_id_btn)

        self._status_label = QLabel("尚未配置同步" if sync_manager is None else "等待下一次同步…")
        layout.addWidget(self._status_label)

        sync_now_btn = QPushButton("立即同步")
        sync_now_btn.setEnabled(sync_manager is not None)
        if sync_manager is not None:
            sync_now_btn.clicked.connect(sync_manager.sync_now)
            sync_manager.state_changed.connect(self._status_label.setText)
        layout.addWidget(sync_now_btn)

        layout.addStretch(1)

    def _save_token(self) -> None:
        token = self._token_edit.text().strip()
        if token:
            crypto.save_gist_token(token)

    def _save_gist_id(self) -> None:
        gist_id = self._gist_id_edit.text().strip()
        if gist_id:
            crypto.save_gist_id(gist_id)

    def _clear_gist_id(self) -> None:
        crypto.clear_gist_id()
        self._gist_id_edit.clear()

    def _copy_gist_id(self) -> None:
        gist_id = self._gist_id_edit.text().strip() or crypto.load_gist_id() or ""
        QApplication.clipboard().setText(gist_id)


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        label = QLabel("DeskToDo\n版本 1.5")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        layout.addStretch(1)
        layout.addWidget(_build_construction_notice())
        layout.addStretch(1)


class ConfigWindow(QWidget):
    _PAGE_INFO = [
        ("桌面组件", "启用、排序和配置桌面上的信息模块"),
        ("UI 调整", "调整主界面外观与启动行为"),
        ("数据同步", "管理 GitHub Gist 同步与连接状态"),
        ("节假日信息", "导入按年份维护的节假日数据"),
        ("显示屏设置", "查看不同显示器组合保存的布局"),
        ("关于", "查看版本与应用信息"),
    ]

    def __init__(
        self,
        store: WidgetConfigStore,
        on_widgets_changed: Callable[[], None],
        sync_manager: Optional[SyncManager] = None,
        current_panel_alpha: int = 230,
        on_panel_alpha_changed: Optional[Callable[[int], None]] = None,
        on_holidays_changed: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("DeskToDo 设置")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Window)
        self.setObjectName("settingsWindow")
        self.resize(860, 600)
        self.setMinimumSize(760, 520)
        self.setStyleSheet(CONFIG_WINDOW_QSS)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 28, 18, 22)
        sidebar_layout.setSpacing(0)

        brand = QLabel("DeskToDo")
        brand.setObjectName("settingsBrand")
        sidebar_layout.addWidget(brand)
        caption = QLabel("设置")
        caption.setObjectName("settingsCaption")
        sidebar_layout.addWidget(caption)
        sidebar_layout.addSpacing(24)

        self._nav_list = QListWidget()
        self._nav_list.setObjectName("settingsNav")
        self._nav_list.addItems([title for title, _subtitle in self._PAGE_INFO])
        self._nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_layout.addWidget(self._nav_list)
        layout.addWidget(sidebar)

        content = QFrame()
        content.setObjectName("settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 26, 30, 26)
        content_layout.setSpacing(0)

        self._page_title = QLabel()
        self._page_title.setObjectName("settingsTitle")
        content_layout.addWidget(self._page_title)
        self._page_subtitle = QLabel()
        self._page_subtitle.setObjectName("settingsSubtitle")
        content_layout.addWidget(self._page_subtitle)
        content_layout.addSpacing(18)

        divider = QFrame()
        divider.setObjectName("settingsDivider")
        divider.setFixedHeight(1)
        content_layout.addWidget(divider)
        content_layout.addSpacing(22)

        self._stack = QStackedWidget()
        content_layout.addWidget(self._stack, 1)
        layout.addWidget(content, 1)

        self._stack.addWidget(WidgetsTab(store, on_widgets_changed))
        self._stack.addWidget(
            UISettingsTab(
                current_panel_alpha,
                on_panel_alpha_changed or (lambda alpha: None),
            )
        )
        self._stack.addWidget(SyncTab(sync_manager))
        self._stack.addWidget(HolidayInfoTab(on_holidays_changed or (lambda: None)))
        self._stack.addWidget(MonitorSettingsTab())
        self._stack.addWidget(AboutTab())

        self._nav_list.currentRowChanged.connect(self._on_page_changed)
        self._nav_list.setCurrentRow(0)

    def _on_page_changed(self, index: int) -> None:
        if not 0 <= index < len(self._PAGE_INFO):
            return
        self._stack.setCurrentIndex(index)
        title, subtitle = self._PAGE_INFO[index]
        self._page_title.setText(title)
        self._page_subtitle.setText(subtitle)
