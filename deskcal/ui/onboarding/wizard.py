"""首次启动引导向导：有边框的临时弹窗，收集 GitHub Gist Token 和天气城市。

完成或跳过后都会标记 onboarding_completed，下次启动不会再弹出；
跳过时不写入任何字段，用户可以之后在设置面板里补填 Token。
"""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from deskcal.ui.desktop_overlay.widgets.registry import WidgetConfigStore
from deskcal.utils import crypto
from deskcal.utils.icons import app_icon


class OnboardingWizard(QDialog):
    def __init__(self, widget_store: WidgetConfigStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 DeskToDo — 首次配置")
        self.setWindowIcon(app_icon())
        self.setFixedWidth(360)
        self._widget_store = widget_store

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("GitHub Gist Token（用于多台电脑之间同步，可稍后在设置面板里补填）"))
        self._token_edit = QLineEdit()
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._token_edit)

        layout.addWidget(QLabel("城市定位（经度,纬度 或 和风天气 LocationID，可留空）"))
        self._city_edit = QLineEdit()
        layout.addWidget(self._city_edit)

        monitor_hint = QLabel(
            "提示：如果你在不同地方接不同显示器使用（比如宿舍接显示器、出门用笔记本自带屏幕），"
            "DeskToDo 会按当前的显示器组合自动记住悬浮窗各自的位置和大小，换显示器组合时会自动"
            "切换到对应的记忆位置，不需要每次手动重新调整。可以在设置面板的「显示屏设置」里查看记了哪些。"
        )
        monitor_hint.setWordWrap(True)
        monitor_hint.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(monitor_hint)

        button_row = QHBoxLayout()
        skip_btn = QPushButton("跳过")
        skip_btn.clicked.connect(self._skip)
        finish_btn = QPushButton("完成")
        finish_btn.clicked.connect(self._finish)
        button_row.addWidget(skip_btn)
        button_row.addStretch(1)
        button_row.addWidget(finish_btn)
        layout.addLayout(button_row)

    def _skip(self) -> None:
        crypto.mark_onboarding_completed()
        self.accept()

    def _finish(self) -> None:
        token = self._token_edit.text().strip()
        if token:
            crypto.save_gist_token(token)

        city = self._city_edit.text().strip()
        if city:
            self._apply_city(city)

        crypto.mark_onboarding_completed()
        self.accept()

    def _apply_city(self, city: str) -> None:
        for index, item in enumerate(self._widget_store.items):
            if item.type_id == "weather":
                config = dict(item.config)
                config["location"] = city
                self._widget_store.update_config(index, config)
                break
        self._widget_store.save()
