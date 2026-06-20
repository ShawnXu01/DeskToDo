"""待办收纳侧栏：存放无具体日期的浮动任务，"待办/完成"两个 tab 是筛选视图，不是删除。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.models import FloatingTask
from deskcal.core.storage import TaskStore
from deskcal.ui.desktop_overlay.task_chip import TaskChipWidget
from deskcal.ui.dialogs.task_dialog import PRIORITY_COLORS, TaskDialog
from deskcal.ui.style_utils import make_scroll_area_transparent


class SidebarTodo(QWidget):
    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self._store = store
        self._showing_completed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        tab_row = QHBoxLayout()
        self._todo_btn = QPushButton("待办")
        self._done_btn = QPushButton("完成")
        for btn in (self._todo_btn, self._done_btn):
            btn.setCheckable(True)
        self._todo_btn.setChecked(True)
        self._todo_btn.clicked.connect(lambda: self._switch_tab(False))
        self._done_btn.clicked.connect(lambda: self._switch_tab(True))
        tab_row.addWidget(self._todo_btn)
        tab_row.addWidget(self._done_btn)
        layout.addLayout(tab_row)

        add_btn = QPushButton("+ 新建待办")
        add_btn.clicked.connect(self._open_create_dialog)
        layout.addWidget(add_btn)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self._list_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        make_scroll_area_transparent(scroll_area)
        layout.addWidget(scroll_area, 1)

        self.render()

    def _switch_tab(self, showing_completed: bool) -> None:
        self._showing_completed = showing_completed
        self._todo_btn.setChecked(not showing_completed)
        self._done_btn.setChecked(showing_completed)
        self.render()

    def _open_create_dialog(self) -> None:
        dialog = TaskDialog(self._store, floating=True, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render()

    def _open_edit_dialog(self, task: FloatingTask) -> None:
        dialog = TaskDialog(self._store, existing_task=task, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render()

    def render(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        tasks = [
            t
            for t in self._store.iter_active_floating_tasks()
            if t.completed == self._showing_completed
        ]
        tasks.sort(key=lambda t: t.sort_key())

        for task in tasks:
            chip = TaskChipWidget(
                name=task.name,
                color=PRIORITY_COLORS[task.priority],
                completed=task.completed,
            )
            chip.editRequested.connect(lambda t=task: self._open_edit_dialog(t))

            def _on_toggle(checked: bool, t: FloatingTask = task) -> None:
                t.set_completed(checked)
                self._store.save()
                self.render()

            chip.toggleCompleteRequested.connect(_on_toggle)
            self._list_layout.insertWidget(self._list_layout.count() - 1, chip)
