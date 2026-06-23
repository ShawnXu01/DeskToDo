"""任务创建/编辑弹窗。日历任务与浮动任务复用同一套弹窗，floating=True 时隐藏日期/周期区域。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.models import DatedTask, FloatingTask, Priority, RecurrenceRule, RecurrenceType
from deskcal.core.storage import TaskStore
from deskcal.ui.dialogs.date_field import DateField
from deskcal.ui.dialogs.mini_calendar_picker import MiniCalendarPicker
from deskcal.utils.icons import app_icon

PRIORITY_COLORS = {
    Priority.RED: "#e53935",
    Priority.GREEN: "#43a047",
    Priority.ORANGE: "#fb8c00",
    Priority.WHITE: "#ffffff",
}

PRIORITY_ORDER = [Priority.WHITE, Priority.ORANGE, Priority.GREEN, Priority.RED]

RECURRENCE_ORDER = [
    RecurrenceType.ONCE,
    RecurrenceType.DAILY_RANGE,
    RecurrenceType.WEEKLY,
    RecurrenceType.SPECIFIC_DATES,
]

RECURRENCE_LABELS = {
    RecurrenceType.ONCE: "单次",
    RecurrenceType.DAILY_RANGE: "范围每天",
    RecurrenceType.WEEKLY: "范围内每周几",
    RecurrenceType.SPECIFIC_DATES: "指定多日",
}

RECURRENCE_HINTS = {
    RecurrenceType.ONCE: "仅在选定的这一天出现",
    RecurrenceType.DAILY_RANGE: "从起始日期到终止日期之间每天都出现",
    RecurrenceType.WEEKLY: "在起止日期范围内，每周选中的星期几出现",
    RecurrenceType.SPECIFIC_DATES: "仅在你选择的具体日期出现",
}

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]  # 对应 isoweekday 1..7

# 弹窗不设自己的样式就会从父级（OverlayWindow）继承白字按钮样式，叠在系统默认白色对话框上
# 等于隐形——这里显式给暗色主题，顺便解决"看不到保存按钮"的问题。
DIALOG_QSS = """
QDialog { background-color: #202020; }
QLabel { color: #cccccc; background: transparent; }
QLineEdit, QComboBox, QDateEdit {
    background-color: #2c2c2c;
    color: #ffffff;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 4px 6px;
}
QCheckBox { color: #cccccc; }
QPushButton {
    background-color: #3a3a3a;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:checked { background-color: #2196f3; }
"""


class TaskDialog(QDialog):
    """existing_task 为 None 时是新建；否则是编辑（沿用原 id，不会产生新任务）。"""

    def __init__(
        self,
        store: TaskStore,
        *,
        default_date: Optional[date] = None,
        existing_task: Optional[Union[DatedTask, FloatingTask]] = None,
        floating: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._existing_task = existing_task
        self._floating = floating or isinstance(existing_task, FloatingTask)
        self._default_date = default_date or date.today()
        self._specific_dates: list[date] = []

        self.setWindowTitle("编辑任务" if existing_task else "新建任务")
        self.setWindowIcon(app_icon())
        self.setFixedWidth(320)
        self.setStyleSheet(DIALOG_QSS)

        self._build_ui()
        self._load_existing()

    # ---------- UI 构建 ----------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("任务名称"))
        self._name_edit = QLineEdit()
        layout.addWidget(self._name_edit)

        layout.addWidget(QLabel("重要等级"))
        priority_row = QHBoxLayout()
        self._priority_group = QButtonGroup(self)
        self._priority_buttons: dict[Priority, QPushButton] = {}
        for priority in PRIORITY_ORDER:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(36, 24)
            color = PRIORITY_COLORS[priority]
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; border: 1px solid #888; }}"
                f"QPushButton:checked {{ border: 2px solid #2196f3; }}"
            )
            self._priority_group.addButton(btn)
            self._priority_buttons[priority] = btn
            priority_row.addWidget(btn)
        self._priority_buttons[Priority.WHITE].setChecked(True)
        layout.addLayout(priority_row)

        self._date_section = QWidget()
        date_layout = QVBoxLayout(self._date_section)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(6)

        date_layout.addWidget(QLabel("周期类型"))
        self._recurrence_combo = QComboBox()
        for rtype in RECURRENCE_ORDER:
            self._recurrence_combo.addItem(RECURRENCE_LABELS[rtype], rtype)
        self._recurrence_combo.currentIndexChanged.connect(self._on_recurrence_changed)
        date_layout.addWidget(self._recurrence_combo)

        self._recurrence_hint = QLabel()
        self._recurrence_hint.setStyleSheet("color: #888888; font-size: 11px;")
        self._recurrence_hint.setWordWrap(True)
        date_layout.addWidget(self._recurrence_hint)

        # 不用 QStackedWidget：它会按所有页面里最高的那个撑高整体尺寸，改成手动 show/hide
        # 让弹窗高度只跟随当前显示的那一页。
        self._recurrence_pages_container = QWidget()
        self._recurrence_pages_layout = QVBoxLayout(self._recurrence_pages_container)
        self._recurrence_pages_layout.setContentsMargins(0, 0, 0, 0)
        self._recurrence_pages: list[QWidget] = []

        once_widget = QWidget()
        once_layout = QVBoxLayout(once_widget)
        once_layout.setContentsMargins(0, 4, 0, 0)
        once_layout.setSpacing(4)
        self._once_date_edit = DateField()
        once_layout.addWidget(self._once_date_edit)
        self._recurrence_pages_layout.addWidget(once_widget)
        self._recurrence_pages.append(once_widget)

        range_widget = QWidget()
        range_layout = QVBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 4, 0, 0)
        range_layout.setSpacing(4)
        range_layout.addWidget(QLabel("起始日期"))
        self._range_start_edit = DateField()
        range_layout.addWidget(self._range_start_edit)
        range_layout.addWidget(QLabel("终止日期"))
        self._range_end_edit = DateField()
        range_layout.addWidget(self._range_end_edit)
        self._recurrence_pages_layout.addWidget(range_widget)
        self._recurrence_pages.append(range_widget)

        weekly_widget = QWidget()
        weekly_layout = QVBoxLayout(weekly_widget)
        weekly_layout.setContentsMargins(0, 4, 0, 0)
        weekly_layout.setSpacing(4)
        weekly_layout.addWidget(QLabel("起始日期"))
        self._weekly_start_edit = DateField()
        weekly_layout.addWidget(self._weekly_start_edit)
        weekly_layout.addWidget(QLabel("终止日期"))
        self._weekly_end_edit = DateField()
        weekly_layout.addWidget(self._weekly_end_edit)
        self._weekday_checks: list[QCheckBox] = []
        for label in WEEKDAY_LABELS:
            cb = QCheckBox(label)
            self._weekday_checks.append(cb)
            weekly_layout.addWidget(cb)
        self._recurrence_pages_layout.addWidget(weekly_widget)
        self._recurrence_pages.append(weekly_widget)

        specific_widget = QWidget()
        specific_layout = QVBoxLayout(specific_widget)
        specific_layout.setContentsMargins(0, 4, 0, 0)
        specific_layout.setSpacing(4)
        self._specific_dates_label = QLabel("未选择日期")
        pick_btn = QPushButton("选择日期")
        pick_btn.clicked.connect(self._open_mini_calendar)
        specific_layout.addWidget(self._specific_dates_label)
        specific_layout.addWidget(pick_btn)
        self._recurrence_pages_layout.addWidget(specific_widget)
        self._recurrence_pages.append(specific_widget)

        date_layout.addWidget(self._recurrence_pages_container)
        layout.addWidget(self._date_section)
        self._on_recurrence_changed(self._recurrence_combo.currentIndex())

        if self._floating:
            self._date_section.setVisible(False)

        button_row = QHBoxLayout()
        if self._existing_task is not None:
            delete_btn = QPushButton("删除")
            delete_btn.clicked.connect(self._on_delete)
            button_row.addWidget(delete_btn)
        button_row.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

    def _on_recurrence_changed(self, index: int) -> None:
        for page_index, page in enumerate(self._recurrence_pages):
            page.setVisible(page_index == index)
        rtype = self._recurrence_combo.itemData(index)
        self._recurrence_hint.setText(RECURRENCE_HINTS[rtype])

        # Qt 把窗口第一次撑到某个高度后会钉成 minimumSize，内容变矮也回不去，要先清掉上下限
        # 再重新计算；processEvents() 是因为隐藏页面后的布局缓存要转一轮事件循环才会刷新。
        # 算完用 setFixedHeight 钉死，顺带让高度也不能被用户手动拖拽（跟宽度一样）。
        QApplication.processEvents()
        self.setMinimumHeight(0)
        self.setMaximumHeight(16_777_215)
        self.layout().invalidate()
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())
        self.setFixedHeight(self.height())

    def _open_mini_calendar(self) -> None:
        picker = MiniCalendarPicker(
            initial_dates=self._specific_dates, anchor_date=self._default_date, mode="multi", parent=self
        )
        if picker.exec() == QDialog.DialogCode.Accepted:
            self._specific_dates = picker.selected_dates()
            self._update_specific_dates_label()

    def _update_specific_dates_label(self) -> None:
        if not self._specific_dates:
            self._specific_dates_label.setText("未选择日期")
        else:
            text = "、".join(d.strftime("%m-%d") for d in self._specific_dates)
            self._specific_dates_label.setText(text)

    # ---------- 数据加载 ----------
    def _load_existing(self) -> None:
        if self._existing_task is None:
            if not self._floating:
                self._once_date_edit.setDate(self._default_date)
                self._range_start_edit.setDate(self._default_date)
                self._range_end_edit.setDate(self._default_date)
            return

        self._name_edit.setText(self._existing_task.name)
        self._priority_buttons[self._existing_task.priority].setChecked(True)

        if isinstance(self._existing_task, DatedTask):
            rule = self._existing_task.recurrence
            index = RECURRENCE_ORDER.index(rule.type)
            self._recurrence_combo.setCurrentIndex(index)
            if rule.type is RecurrenceType.ONCE:
                self._once_date_edit.setDate(rule.date)
            elif rule.type is RecurrenceType.DAILY_RANGE:
                self._range_start_edit.setDate(rule.start)
                self._range_end_edit.setDate(rule.end)
            elif rule.type is RecurrenceType.WEEKLY:
                if rule.start is not None:
                    self._weekly_start_edit.setDate(rule.start)
                if rule.end is not None:
                    self._weekly_end_edit.setDate(rule.end)
                for weekday in rule.weekdays:
                    self._weekday_checks[weekday - 1].setChecked(True)
            elif rule.type is RecurrenceType.SPECIFIC_DATES:
                self._specific_dates = list(rule.dates)
                self._update_specific_dates_label()

    # ---------- 保存/删除 ----------
    def _selected_priority(self) -> Priority:
        for priority, btn in self._priority_buttons.items():
            if btn.isChecked():
                return priority
        return Priority.WHITE

    def _build_recurrence_rule(self) -> Optional[RecurrenceRule]:
        rtype = self._recurrence_combo.currentData()
        if rtype is RecurrenceType.ONCE:
            return RecurrenceRule(type=rtype, date=self._once_date_edit.date())
        if rtype is RecurrenceType.DAILY_RANGE:
            start = self._range_start_edit.date()
            end = self._range_end_edit.date()
            if start > end:
                QMessageBox.warning(self, "日期错误", "起始日期不能晚于终止日期")
                return None
            return RecurrenceRule(type=rtype, start=start, end=end)
        if rtype is RecurrenceType.WEEKLY:
            weekdays = [i + 1 for i, cb in enumerate(self._weekday_checks) if cb.isChecked()]
            if not weekdays:
                QMessageBox.warning(self, "未选择", "请至少选择一个星期")
                return None
            start = self._weekly_start_edit.date()
            end = self._weekly_end_edit.date()
            if start > end:
                QMessageBox.warning(self, "日期错误", "起始日期不能晚于终止日期")
                return None
            return RecurrenceRule(type=rtype, start=start, end=end, weekdays=weekdays)
        if rtype is RecurrenceType.SPECIFIC_DATES:
            if not self._specific_dates:
                QMessageBox.warning(self, "未选择", "请至少选择一个日期")
                return None
            return RecurrenceRule(type=rtype, dates=list(self._specific_dates))
        raise AssertionError(f"未知周期类型: {rtype}")

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "未填写", "请输入任务名称")
            return
        priority = self._selected_priority()

        if self._floating:
            if isinstance(self._existing_task, FloatingTask):
                self._existing_task.name = name
                self._existing_task.priority = priority
                self._existing_task.updated_at = datetime.now()
            else:
                task = FloatingTask.create(name, priority)
                self._store.add_floating_task(task)
        else:
            rule = self._build_recurrence_rule()
            if rule is None:
                return
            if isinstance(self._existing_task, DatedTask):
                self._existing_task.name = name
                self._existing_task.priority = priority
                self._existing_task.recurrence = rule
                self._existing_task.updated_at = datetime.now()
            else:
                task = DatedTask.create(name, priority, rule)
                self._store.add_dated_task(task)

        self._store.save()
        self.accept()

    def _on_delete(self) -> None:
        if self._existing_task is None:
            return
        confirm = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条任务吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._store.soft_delete(self._existing_task.id)
            self._store.save()
            self.accept()
