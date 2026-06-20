"""配置面板：同程序的第二个窗口，有边框。左侧导航 + 右侧内容。

桌面组件 tab：增删启用/拖拽排序用上下按钮代替/单个组件设置。
数据同步 tab：填 Gist Token（保存后需重启生效）+ 立即同步 + 状态显示。
关于 tab：版本信息 + 节假日数据可用性检查（用户主动触发，可以有失败提示）。
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from deskcal.services.sync_manager import SyncManager
from deskcal.ui.desktop_overlay.widgets.registry import WIDGET_DEFINITIONS, WidgetConfigStore
from deskcal.utils import crypto

_BACKGROUND_IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "images" / "config_background.png"
_BACKGROUND_TINT = QColor(0, 0, 0, 210)

CONFIG_WINDOW_QSS = """
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
QLineEdit, QDateEdit, QDateTimeEdit {
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


class WeatherSettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("天气设置")
        self._config = dict(config)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("城市定位（经度,纬度 或 和风天气 LocationID）"))
        self._location_edit = QLineEdit(self._config.get("location", ""))
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
        self._items: list[dict] = list(config.get("items", []))

        layout = QVBoxLayout(self)
        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

        add_row = QHBoxLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("标题，如 AAAI 截稿")
        self._deadline_edit = QDateTimeEdit(datetime.now())
        self._deadline_edit.setCalendarPopup(True)
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_item)
        add_row.addWidget(self._title_edit)
        add_row.addWidget(self._deadline_edit)
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
        for item in self._items:
            self._list_widget.addItem(f"{item['title']} — {item['deadline']}")

    def _add_item(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            return
        deadline_iso = self._deadline_edit.dateTime().toPyDateTime().isoformat()
        self._items.append({"title": title, "deadline": deadline_iso})
        self._title_edit.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        row = self._list_widget.currentRow()
        if row >= 0:
            del self._items[row]
            self._refresh_list()

    def result_config(self) -> dict:
        return {"items": self._items}


class ProgressSettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("进度条设置")
        self._items: list[dict] = list(config.get("items", []))

        layout = QVBoxLayout(self)
        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

        add_row = QHBoxLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("标题，如 本学期进度")
        self._start_edit = QDateEdit(date.today())
        self._start_edit.setCalendarPopup(True)
        self._end_edit = QDateEdit(date.today())
        self._end_edit.setCalendarPopup(True)
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
        for item in self._items:
            self._list_widget.addItem(f"{item['title']} — {item['start']} ~ {item['end']}")

    def _add_item(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            return
        start_iso = self._start_edit.date().toPyDate().isoformat()
        end_iso = self._end_edit.date().toPyDate().isoformat()
        self._items.append({"title": title, "start": start_iso, "end": end_iso})
        self._title_edit.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        row = self._list_widget.currentRow()
        if row >= 0:
            del self._items[row]
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


class SyncTab(QWidget):
    """Gist Token 填写 + 立即同步 + 状态显示。Token 改动需要重启 DeskCal 才会生效，
    不在面板里动态重建同步线程，避免运行时热切换带来的复杂度。"""

    def __init__(self, sync_manager: Optional[SyncManager], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("GitHub Gist Token（保存后需重启 DeskCal 才会生效）"))
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

        label = QLabel("DeskCal\n版本 0.1（开发中）")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        check_btn = QPushButton("检查今年的节假日数据")
        check_btn.clicked.connect(self._check_holiday_data)
        layout.addWidget(check_btn)

        layout.addStretch(1)

    def _check_holiday_data(self) -> None:
        from deskcal.services.lunar_holiday import get_day_lunar_info

        info = get_day_lunar_info(date.today())
        if info.is_statutory_holiday is None:
            QMessageBox.warning(
                self,
                "节假日数据",
                "今年的法定节假日数据暂不可用，需要更新 chinese-calendar 依赖包。",
            )
        else:
            QMessageBox.information(self, "节假日数据", "今年的法定节假日数据可用。")


class ConfigWindow(QWidget):
    def __init__(
        self,
        store: WidgetConfigStore,
        on_widgets_changed: Callable[[], None],
        sync_manager: Optional[SyncManager] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("DeskCal 设置")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(700, 500)
        self.setStyleSheet(CONFIG_WINDOW_QSS)

        self._background = QPixmap(str(_BACKGROUND_IMAGE_PATH))

        layout = QHBoxLayout(self)

        nav_list = QListWidget()
        nav_list.addItems(["桌面组件", "数据同步", "关于"])
        nav_list.setFixedWidth(140)
        layout.addWidget(nav_list)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self._stack.addWidget(WidgetsTab(store, on_widgets_changed))
        self._stack.addWidget(SyncTab(sync_manager))
        self._stack.addWidget(AboutTab())

        nav_list.currentRowChanged.connect(self._stack.setCurrentIndex)
        nav_list.setCurrentRow(0)

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
        painter.fillRect(self.rect(), _BACKGROUND_TINT)
        painter.end()
        super().paintEvent(event)
