"""配置面板：同程序的第二个窗口，有边框。左侧导航 + 右侧内容，各 tab 见下方对应类的 docstring。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
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

from deskcal.core.storage import get_data_dir, list_window_profiles, load_appearance, save_appearance
from deskcal.services import autostart
from deskcal.services.lunar_holiday import get_holidays_file
from deskcal.services.sync_manager import SyncManager
from deskcal.ui.desktop_overlay.widgets.registry import WIDGET_DEFINITIONS, WidgetConfigStore
from deskcal.ui.dialogs.date_field import DateField
from deskcal.ui.style_utils import ElidingLabel
from deskcal.utils import crypto
from deskcal.utils.icons import app_icon
from deskcal.utils.monitor import compute_monitor_signature

_BACKGROUND_IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "config_background.png"

CONFIG_WINDOW_QSS = (
    """
QWidget { color: #ffffff; }
QLabel { background: transparent; }
QDialog { background-color: #1a1a1a; }
QPushButton {
    background-color: rgba(255, 255, 255, 30);
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
}
QPushButton:hover { background-color: rgba(255, 255, 255, 60); }
QPushButton:checked { background-color: rgba(255, 255, 255, 90); }
QLineEdit, QTimeEdit {
    background-color: rgba(255, 255, 255, 30);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 4px;
    padding: 2px 4px;
}
QListWidget {
    background-color: rgba(0, 0, 0, 80);
    color: #ffffff;
    border: none;
}
QListWidget::item:selected { background-color: rgba(255, 255, 255, 60); }
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
}


class WidgetsTab(QWidget):
    def __init__(self, store: WidgetConfigStore, on_changed: Callable[[], None], parent=None):
        super().__init__(parent)
        self._store = store
        self._on_changed = on_changed

        self._layout = QVBoxLayout(self)
        self._rows_container = QVBoxLayout()
        self._layout.addLayout(self._rows_container)
        self._layout.addStretch(1)
        self._layout.addWidget(_build_construction_notice())
        self._layout.addStretch(1)

        self.render()

    def render(self) -> None:
        while self._rows_container.count():
            item = self._rows_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, instance in enumerate(self._store.items):
            definition = WIDGET_DEFINITIONS[instance.type_id]

            row = QWidget()
            row_layout = QHBoxLayout(row)

            enabled_checkbox = QPushButton("已启用" if instance.enabled else "已关闭")
            enabled_checkbox.setCheckable(True)
            enabled_checkbox.setChecked(instance.enabled)
            enabled_checkbox.toggled.connect(lambda checked, i=index: self._toggle_enabled(i, checked))
            row_layout.addWidget(enabled_checkbox)

            name_label = QLabel(definition.display_name)
            row_layout.addWidget(name_label, 1)

            up_btn = QPushButton("上移")
            up_btn.clicked.connect(lambda _checked=False, i=index: self._move_up(i))
            row_layout.addWidget(up_btn)

            down_btn = QPushButton("下移")
            down_btn.clicked.connect(lambda _checked=False, i=index: self._move_down(i))
            row_layout.addWidget(down_btn)

            settings_btn = QPushButton("设置")
            settings_btn.setEnabled(definition.configurable)
            settings_btn.clicked.connect(lambda _checked=False, i=index: self._open_settings(i))
            row_layout.addWidget(settings_btn)

            self._rows_container.addWidget(row)

    def _toggle_enabled(self, index: int, checked: bool) -> None:
        self._store.set_enabled(index, checked)
        self._store.save()
        self._on_changed()
        self.render()

    def _move_up(self, index: int) -> None:
        self._store.move_up(index)
        self._store.save()
        self._on_changed()
        self.render()

    def _move_down(self, index: int) -> None:
        self._store.move_down(index)
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
    """界面外观调整：日历悬浮窗背板透明度 + 设置界面自己的背景图/背板透明度。"""

    def __init__(
        self,
        current_panel_alpha: int,
        on_panel_alpha_changed: Callable[[int], None],
        current_config_panel_alpha: int,
        on_config_panel_alpha_changed: Callable[[int], None],
        on_config_background_changed: Callable[[Optional[str]], None],
        parent=None,
    ):
        super().__init__(parent)
        self._on_panel_alpha_changed = on_panel_alpha_changed
        self._on_config_panel_alpha_changed = on_config_panel_alpha_changed
        self._on_config_background_changed = on_config_background_changed

        layout = QVBoxLayout(self)
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

        layout.addWidget(QLabel("设置界面背板透明度"))

        config_row = QHBoxLayout()
        self._config_slider = QSlider(Qt.Orientation.Horizontal)
        self._config_slider.setRange(0, 100)
        self._config_slider.setValue(round(current_config_panel_alpha / 255 * 100))
        self._config_value_label = QLabel(f"{self._config_slider.value()}%")
        self._config_slider.valueChanged.connect(self._on_config_slider_changed)
        config_row.addWidget(self._config_slider, 1)
        config_row.addWidget(self._config_value_label)
        layout.addLayout(config_row)

        layout.addWidget(QLabel("设置界面背景图"))
        upload_btn = QPushButton("上传背景图...")
        upload_btn.clicked.connect(self._upload_background)
        layout.addWidget(upload_btn)

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

    def _on_config_slider_changed(self, percent: int) -> None:
        self._config_value_label.setText(f"{percent}%")
        alpha = round(percent / 100 * 255)
        self._on_config_panel_alpha_changed(alpha)

    def _upload_background(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择背景图", "", "图片文件 (*.png *.jpg *.jpeg *.bmp)")
        if not file_path:
            return
        suffix = Path(file_path).suffix
        dest = get_data_dir() / f"custom_config_background{suffix}"
        try:
            dest.write_bytes(Path(file_path).read_bytes())
        except OSError as exc:
            QMessageBox.warning(self, "上传失败", f"无法读取或保存图片：{exc}")
            return
        self._on_config_background_changed(str(dest))


class HolidayInfoTab(QWidget):
    """法定节假日每年安排不同，需要用户自行下载当年数据导入；母亲节/父亲节等公式类特殊日期不需要导入，自动计算。"""

    def __init__(self, on_holidays_changed: Callable[[], None], parent=None):
        super().__init__(parent)
        self._on_holidays_changed = on_holidays_changed

        layout = QVBoxLayout(self)
        hint = QLabel(
            "法定节假日（春节、国庆节等）每年的具体安排由国务院每年发布，程序内置了发布时已知年份的"
            "默认数据，但以后年份需要你自己更新。\n\n"
            "获取方式：搜索“国务院办公厅 关于 X 年部分节假日安排的通知”（新华社/中国政府网会发布），"
            "整理成如下格式的 JSON 文件（日期: 节日名）：\n\n"
            '{\n  "2027-01-01": "元旦",\n  "2027-05-01": "劳动节"\n}\n\n'
            "整理好后点击下面的按钮选择该文件导入即可，日历会立即按新数据显示。\n"
            "（母亲节、父亲节等按公式计算的特殊日期不受影响，不需要导入。）"
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

    COLUMNS = ["显示器签名", "X", "Y", "宽度", "高度", "组件区宽度", "侧栏宽度"]
    COLUMN_STRETCH = [3, 1, 1, 1, 1, 1, 1]

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "DeskToDo 会按你当前接的显示器组合（比如单独用笔记本屏幕、还是外接了别的显示器）"
            "自动记住悬浮窗的位置、大小和组件区宽度。换一套显示器组合时会自动套用对应记录；"
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
                geometry.get("widget_area_width"),
                geometry.get("sidebar_width"),
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


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        label = QLabel("DeskToDo\n版本 0.1（开发中）")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        layout.addStretch(1)
        layout.addWidget(_build_construction_notice())
        layout.addStretch(1)


class ConfigWindow(QWidget):
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
        self.resize(700, 500)
        self.setStyleSheet(CONFIG_WINDOW_QSS)

        appearance = load_appearance()
        self._config_panel_alpha = appearance["config_panel_alpha"]
        self._load_background(appearance.get("config_background_path"))

        layout = QHBoxLayout(self)

        nav_list = QListWidget()
        nav_list.addItems(["桌面组件", "UI调整", "数据同步", "节假日信息", "显示屏设置", "关于"])
        nav_list.setFixedWidth(140)
        layout.addWidget(nav_list)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self._stack.addWidget(WidgetsTab(store, on_widgets_changed))
        self._stack.addWidget(
            UISettingsTab(
                current_panel_alpha,
                on_panel_alpha_changed or (lambda alpha: None),
                self._config_panel_alpha,
                self._on_config_panel_alpha_changed,
                self._on_config_background_changed,
            )
        )
        self._stack.addWidget(SyncTab(sync_manager))
        self._stack.addWidget(HolidayInfoTab(on_holidays_changed or (lambda: None)))
        self._stack.addWidget(MonitorSettingsTab())
        self._stack.addWidget(AboutTab())

        nav_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        nav_list.setCurrentRow(0)

    def _load_background(self, custom_path: Optional[str]) -> None:
        path = Path(custom_path) if custom_path else _BACKGROUND_IMAGE_PATH
        pixmap = QPixmap(str(path))
        self._background = pixmap if not pixmap.isNull() else QPixmap(str(_BACKGROUND_IMAGE_PATH))

    def _on_config_panel_alpha_changed(self, alpha: int) -> None:
        self._config_panel_alpha = alpha
        save_appearance(config_panel_alpha=alpha)
        self.update()

    def _on_config_background_changed(self, path: Optional[str]) -> None:
        self._load_background(path)
        save_appearance(config_background_path=path)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not self._background.isNull():
            scaled = self._background.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._config_panel_alpha))
        painter.end()
        super().paintEvent(event)
