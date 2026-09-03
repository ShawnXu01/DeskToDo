"""课表设置：Term 管理和课程录入。"""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, time
from typing import Optional

from PyQt6.QtCore import QTime, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.schedule_models import CourseEntry, Term
from deskcal.core.schedule_storage import ScheduleStore
from deskcal.ui.dialogs.date_field import DateField
from deskcal.ui.schedule.schedule_import_dialog import ScheduleImportDialog
from deskcal.utils.icons import app_icon

COURSE_COLORS = [
    ("Butter", "#F2E6A7"),
    ("Sage", "#CFE3C1"),
    ("Powder Blue", "#C9E2EA"),
    ("Blush", "#EBCFD0"),
    ("Lavender", "#DED0EA"),
    ("Peach", "#F1D6B8"),
    ("Mint", "#C5E5DA"),
    ("Periwinkle", "#CDD5F2"),
]

WEEKDAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

SCHEDULE_QSS = """
QDialog, QWidget { background-color: #181818; color: #f2f2f2; }
QLabel { background: transparent; }
QLineEdit, QTimeEdit, QSpinBox, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget {
    background-color: #242424;
    color: #f2f2f2;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 4px;
}
QPushButton {
    background-color: #343434;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #454545; }
QPushButton:checked { background-color: #123d70; }
QPushButton:disabled { color: #777777; background-color: #292929; }
QHeaderView::section { background-color: #242424; color: #dddddd; padding: 6px; border: none; }
"""


def format_weekdays(days: list[int]) -> str:
    return "/".join(WEEKDAY_NAMES[day - 1] for day in days)


class TermEditDialog(QDialog):
    def __init__(self, term: Optional[Term] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑学期" if term else "新增学期")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(SCHEDULE_QSS)
        self.setFixedWidth(360)

        today = date.today()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("学期名称"))
        self._name = QLineEdit(term.name if term else "")
        self._name.setPlaceholderText("例如 Fall - 2026")
        layout.addWidget(self._name)

        layout.addWidget(QLabel("开始日期"))
        self._start = DateField(term.start_date if term else today)
        layout.addWidget(self._start)
        layout.addWidget(QLabel("结束日期"))
        self._end = DateField(term.end_date if term else today + timedelta(days=120))
        layout.addWidget(self._end)

        buttons = QHBoxLayout()
        keep_btn = QPushButton("取消")
        keep_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存学期")
        save_btn.clicked.connect(self._validate)
        buttons.addStretch(1)
        buttons.addWidget(keep_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def _validate(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "缺少学期名称", "请输入学期名称，例如 Fall - 2026。")
            return
        if self._start.date() > self._end.date():
            QMessageBox.warning(self, "日期范围不正确", "学期结束日期必须晚于或等于开始日期。")
            return
        self.accept()

    def values(self) -> tuple[str, date, date]:
        return self._name.text().strip(), self._start.date(), self._end.date()


class CourseEditDialog(QDialog):
    def __init__(self, course: Optional[CourseEntry] = None, default_color: str = COURSE_COLORS[0][1], parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑课程" if course else "新增课程")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(SCHEDULE_QSS)
        self.setMinimumWidth(470)
        self._selected_color = course.color if course else default_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        name_row = QHBoxLayout()
        code_col = QVBoxLayout()
        code_col.addWidget(QLabel("课程代码 *"))
        self._code = QLineEdit(course.code if course else "")
        self._code.setPlaceholderText("ECE340")
        code_col.addWidget(self._code)
        title_col = QVBoxLayout()
        title_col.addWidget(QLabel("课程全名"))
        self._title = QLineEdit(course.title if course else "")
        self._title.setPlaceholderText("Fields and Waves")
        title_col.addWidget(self._title)
        name_row.addLayout(code_col, 1)
        name_row.addLayout(title_col, 2)
        layout.addLayout(name_row)

        layout.addWidget(QLabel("上课日 *"))
        self._unscheduled = QCheckBox("无固定时间（异步网课或时间待定）")
        self._unscheduled.setChecked(bool(course and course.start_time is None))
        self._unscheduled.toggled.connect(self._on_unscheduled_changed)
        layout.addWidget(self._unscheduled)
        weekday_row = QHBoxLayout()
        self._weekday_buttons: list[QPushButton] = []
        selected_days = set(course.weekdays if course else [])
        for index, label in enumerate(WEEKDAY_LABELS, start=1):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setFixedSize(42, 32)
            button.setToolTip(WEEKDAY_NAMES[index - 1])
            button.setChecked(index in selected_days)
            self._weekday_buttons.append(button)
            weekday_row.addWidget(button)
        weekday_row.addStretch(1)
        layout.addLayout(weekday_row)

        time_row = QHBoxLayout()
        start_col = QVBoxLayout()
        start_col.addWidget(QLabel("开始时间 *"))
        self._start_time = QTimeEdit()
        self._start_time.setDisplayFormat("h:mm AP")
        initial_start = course.start_time if course and course.start_time else time(9, 0)
        self._start_time.setTime(QTime(initial_start.hour, initial_start.minute))
        start_col.addWidget(self._start_time)
        end_col = QVBoxLayout()
        end_col.addWidget(QLabel("结束时间 *"))
        self._end_time = QTimeEdit()
        self._end_time.setDisplayFormat("h:mm AP")
        initial_end = course.end_time if course and course.end_time else time(9, 50)
        self._end_time.setTime(QTime(initial_end.hour, initial_end.minute))
        end_col.addWidget(self._end_time)
        time_row.addLayout(start_col)
        time_row.addLayout(end_col)
        time_row.addStretch(1)
        layout.addLayout(time_row)

        detail_row = QHBoxLayout()
        location_col = QVBoxLayout()
        location_col.addWidget(QLabel("地点"))
        self._location = QLineEdit(course.location if course else "")
        self._location.setPlaceholderText("ECEB 1013")
        location_col.addWidget(self._location)
        instructor_col = QVBoxLayout()
        instructor_col.addWidget(QLabel("教师"))
        self._instructor = QLineEdit(course.instructor if course else "")
        self._instructor.setPlaceholderText("Professor Smith")
        instructor_col.addWidget(self._instructor)
        detail_row.addLayout(location_col)
        detail_row.addLayout(instructor_col)
        layout.addLayout(detail_row)

        layout.addWidget(QLabel("课程资料（Syllabus / Course Web，可选）"))
        resource_row = QHBoxLayout()
        self._course_resource = QLineEdit(course.course_resource if course else "")
        self._course_resource.setPlaceholderText("粘贴 https:// 网址，或选择本地 PDF")
        choose_resource = QPushButton("选择 PDF")
        choose_resource.clicked.connect(self._choose_course_resource)
        resource_row.addWidget(self._course_resource, 1)
        resource_row.addWidget(choose_resource)
        layout.addLayout(resource_row)

        layout.addWidget(QLabel("课程颜色"))
        color_row = QHBoxLayout()
        self._color_group = QButtonGroup(self)
        self._color_group.setExclusive(True)
        for index, (name, color) in enumerate(COURSE_COLORS):
            button = QPushButton()
            button.setCheckable(True)
            button.setFixedSize(34, 28)
            button.setToolTip(name)
            button.setStyleSheet(
                f"QPushButton {{ background-color: {color}; border: 1px solid #555555; }}"
                "QPushButton:checked { border: 3px solid #ffffff; }"
            )
            button.setChecked(color.lower() == self._selected_color.lower())
            button.clicked.connect(lambda _checked=False, value=color: self._set_color(value))
            self._color_group.addButton(button, index)
            color_row.addWidget(button)
        color_row.addStretch(1)
        layout.addLayout(color_row)

        layout.addWidget(QLabel("备注"))
        self._notes = QTextEdit(course.notes if course else "")
        self._notes.setPlaceholderText("可选：考试安排、进门方式或其他提醒")
        self._notes.setFixedHeight(70)
        layout.addWidget(self._notes)

        buttons = QHBoxLayout()
        keep_btn = QPushButton("取消")
        keep_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存课程")
        save_btn.clicked.connect(self._validate)
        buttons.addStretch(1)
        buttons.addWidget(keep_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)
        self._on_unscheduled_changed(self._unscheduled.isChecked())

    def _set_color(self, color: str) -> None:
        self._selected_color = color

    def _choose_course_resource(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择课程 Syllabus",
            "",
            "PDF 文件 (*.pdf)",
        )
        if file_name:
            self._course_resource.setText(file_name)

    def _on_unscheduled_changed(self, checked: bool) -> None:
        for button in self._weekday_buttons:
            button.setEnabled(not checked)
        self._start_time.setEnabled(not checked)
        self._end_time.setEnabled(not checked)

    def _validate(self) -> None:
        if not self._code.text().strip():
            QMessageBox.warning(self, "缺少课程代码", "请输入课程代码，例如 ECE340。")
            return
        if not self._unscheduled.isChecked() and not any(button.isChecked() for button in self._weekday_buttons):
            QMessageBox.warning(self, "缺少上课日", "请至少选择一个上课日。")
            return
        start = self._start_time.time().toPyTime()
        end = self._end_time.time().toPyTime()
        if not self._unscheduled.isChecked() and start >= end:
            QMessageBox.warning(self, "时间范围不正确", "课程结束时间必须晚于开始时间。")
            return
        self.accept()

    def values(self) -> dict:
        unscheduled = self._unscheduled.isChecked()
        return {
            "code": self._code.text().strip(),
            "title": self._title.text().strip(),
            "instructor": self._instructor.text().strip(),
            "location": self._location.text().strip(),
            "weekdays": [] if unscheduled else [
                index for index, button in enumerate(self._weekday_buttons, start=1) if button.isChecked()
            ],
            "start_time": None if unscheduled else self._start_time.time().toPyTime(),
            "end_time": None if unscheduled else self._end_time.time().toPyTime(),
            "color": self._selected_color,
            "notes": self._notes.toPlainText().strip(),
            "course_resource": self._course_resource.text().strip(),
        }


class ScheduleSettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("课表设置")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(SCHEDULE_QSS)
        self.resize(900, 600)
        self.setMinimumSize(760, 500)
        self._config = dict(config)
        loaded_store = ScheduleStore()
        loaded_store.load()
        self._store = copy.deepcopy(loaded_store)
        self._course_ids: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        display_row = QHBoxLayout()
        self._show_weekends = QCheckBox("显示周末")
        self._show_weekends.setChecked(self._config.get("show_weekends", False))
        display_row.addWidget(self._show_weekends)
        display_row.addWidget(QLabel("时间格式"))
        self._time_format = QComboBox()
        self._time_format.addItem("12 小时（1PM）", "12h")
        self._time_format.addItem("24 小时（13:00）", "24h")
        index = self._time_format.findData(self._config.get("time_format", "12h"))
        self._time_format.setCurrentIndex(max(0, index))
        display_row.addWidget(self._time_format)
        display_row.addStretch(1)
        outer.addLayout(display_row)

        reminder_row = QHBoxLayout()
        self._notifications_enabled = QCheckBox("启用课前提醒")
        self._notifications_enabled.setChecked(self._config.get("notifications_enabled", False))
        reminder_row.addWidget(self._notifications_enabled)
        reminder_row.addSpacing(10)
        self._reminder_label = QLabel("提前")
        reminder_row.addWidget(self._reminder_label)
        self._reminder_minutes = QSpinBox()
        self._reminder_minutes.setRange(1, 180)
        self._reminder_minutes.setSuffix(" 分钟")
        self._reminder_minutes.setValue(self._config.get("reminder_minutes", 20))
        reminder_row.addWidget(self._reminder_minutes)
        reminder_row.addWidget(QLabel("通过 Windows 通知提醒"))
        reminder_row.addStretch(1)
        outer.addLayout(reminder_row)
        self._notifications_enabled.toggled.connect(self._on_notifications_toggled)
        self._on_notifications_toggled(self._notifications_enabled.isChecked())

        content = QHBoxLayout()
        content.setSpacing(12)

        term_panel = QFrame()
        term_panel.setFixedWidth(230)
        term_layout = QVBoxLayout(term_panel)
        term_layout.setContentsMargins(0, 0, 0, 0)
        term_layout.addWidget(QLabel("学期"))
        self._term_list = QListWidget()
        self._term_list.currentItemChanged.connect(self._on_term_changed)
        term_layout.addWidget(self._term_list, 1)
        add_term = QPushButton("新增学期")
        add_term.clicked.connect(self._add_term)
        term_layout.addWidget(add_term)
        term_actions = QHBoxLayout()
        edit_term = QPushButton("编辑")
        edit_term.clicked.connect(self._edit_term)
        copy_term = QPushButton("复制")
        copy_term.clicked.connect(self._duplicate_term)
        term_actions.addWidget(edit_term)
        term_actions.addWidget(copy_term)
        term_layout.addLayout(term_actions)
        term_actions2 = QHBoxLayout()
        archive_term = QPushButton("归档/恢复")
        archive_term.clicked.connect(self._toggle_archive)
        delete_term = QPushButton("删除")
        delete_term.clicked.connect(self._delete_term)
        term_actions2.addWidget(archive_term)
        term_actions2.addWidget(delete_term)
        term_layout.addLayout(term_actions2)
        content.addWidget(term_panel)

        course_panel = QFrame()
        course_layout = QVBoxLayout(course_panel)
        course_layout.setContentsMargins(0, 0, 0, 0)
        self._course_title = QLabel("课程")
        self._course_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        course_layout.addWidget(self._course_title)
        self._course_table = QTableWidget(0, 4)
        self._course_table.setHorizontalHeaderLabels(["课程", "上课日", "时间", "地点"])
        self._course_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._course_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._course_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._course_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._course_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._course_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._course_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._course_table.doubleClicked.connect(self._edit_course)
        course_layout.addWidget(self._course_table, 1)
        course_actions = QHBoxLayout()
        add_course = QPushButton("新增课程")
        add_course.clicked.connect(self._add_course)
        edit_course = QPushButton("编辑课程")
        edit_course.clicked.connect(self._edit_course)
        copy_course = QPushButton("复制课程")
        copy_course.clicked.connect(self._duplicate_course)
        import_courses = QPushButton("AI 图片导入")
        import_courses.clicked.connect(self._import_courses)
        delete_course = QPushButton("删除课程")
        delete_course.clicked.connect(self._delete_course)
        course_actions.addWidget(add_course)
        course_actions.addWidget(edit_course)
        course_actions.addWidget(copy_course)
        course_actions.addWidget(import_courses)
        course_actions.addStretch(1)
        course_actions.addWidget(delete_course)
        course_layout.addLayout(course_actions)
        content.addWidget(course_panel, 1)
        outer.addLayout(content, 1)

        bottom = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存课表")
        save_btn.clicked.connect(self._save)
        bottom.addStretch(1)
        bottom.addWidget(cancel_btn)
        bottom.addWidget(save_btn)
        outer.addLayout(bottom)

        self._refresh_terms(self._store.active_term_id)

    def _selected_term(self) -> Optional[Term]:
        item = self._term_list.currentItem()
        return self._store.terms.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _on_notifications_toggled(self, enabled: bool) -> None:
        self._reminder_label.setEnabled(enabled)
        self._reminder_minutes.setEnabled(enabled)

    def _selected_course(self) -> Optional[CourseEntry]:
        row = self._course_table.currentRow()
        term = self._selected_term()
        if term is None or row < 0 or row >= len(self._course_ids):
            return None
        return term.get_course(self._course_ids[row])

    def _refresh_terms(self, select_id: Optional[str] = None) -> None:
        self._term_list.blockSignals(True)
        self._term_list.clear()
        terms = sorted(self._store.terms.values(), key=lambda term: (term.archived, term.start_date, term.name.casefold()))
        target_row = -1
        for row, term in enumerate(terms):
            label = f"{term.name}  · 已归档" if term.archived else term.name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, term.id)
            self._term_list.addItem(item)
            if term.id == select_id:
                target_row = row
        self._term_list.blockSignals(False)
        if target_row < 0 and self._term_list.count():
            target_row = 0
        self._term_list.setCurrentRow(target_row)
        self._refresh_courses()

    def _on_term_changed(self, current, previous) -> None:
        term = self._selected_term()
        if term is not None:
            self._store.active_term_id = term.id
        self._refresh_courses()

    def _refresh_courses(self) -> None:
        term = self._selected_term()
        self._course_ids = []
        self._course_table.setRowCount(0)
        self._course_title.setText("课程" if term is None else f"{term.name} · 课程")
        if term is None:
            return
        for row, course in enumerate(term.sorted_courses()):
            self._course_ids.append(course.id)
            self._course_table.insertRow(row)
            code_item = QTableWidgetItem(course.code)
            self._course_table.setItem(row, 0, code_item)
            self._course_table.setItem(row, 1, QTableWidgetItem(format_weekdays(course.weekdays) or "—"))
            time_text = (
                f"{course.start_time.strftime('%H:%M')}–{course.end_time.strftime('%H:%M')}"
                if course.start_time and course.end_time
                else "无固定时间"
            )
            self._course_table.setItem(row, 2, QTableWidgetItem(time_text))
            self._course_table.setItem(row, 3, QTableWidgetItem(course.location or "—"))

    def _add_term(self) -> None:
        dialog = TermEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, start, end = dialog.values()
        term = Term.create(name, start, end)
        self._store.add_term(term)
        self._refresh_terms(term.id)

    def _edit_term(self) -> None:
        term = self._selected_term()
        if term is None:
            return
        dialog = TermEditDialog(term, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term.name, term.start_date, term.end_date = dialog.values()
        term.updated_at = datetime.now()
        self._refresh_terms(term.id)

    def _duplicate_term(self) -> None:
        term = self._selected_term()
        if term is None:
            return
        duplicate = self._store.duplicate_term(term.id, f"{term.name} Copy")
        self._refresh_terms(duplicate.id)

    def _toggle_archive(self) -> None:
        term = self._selected_term()
        if term is None:
            return
        term.archived = not term.archived
        term.updated_at = datetime.now()
        self._refresh_terms(term.id)

    def _delete_term(self) -> None:
        term = self._selected_term()
        if term is None:
            return
        message = f"删除学期“{term.name}”？"
        if term.courses:
            message += f"\n这会同时永久删除其中 {len(term.courses)} 门课程。"
        result = QMessageBox.question(
            self,
            "删除学期",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._store.remove_term(term.id)
            self._refresh_terms(self._store.active_term_id)

    def _next_color(self, term: Term) -> str:
        return COURSE_COLORS[len(term.courses) % len(COURSE_COLORS)][1]

    def _add_course(self) -> None:
        term = self._selected_term()
        if term is None:
            QMessageBox.information(self, "先创建学期", "创建一个学期后才能添加课程。")
            return
        dialog = CourseEditDialog(default_color=self._next_color(term), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term.add_course(CourseEntry.create(**dialog.values()))
        self._refresh_courses()

    def _edit_course(self, *_args) -> None:
        term = self._selected_term()
        course = self._selected_course()
        if term is None or course is None:
            return
        dialog = CourseEditDialog(course, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        for key, value in dialog.values().items():
            setattr(course, key, value)
        course.updated_at = datetime.now()
        term.updated_at = course.updated_at
        self._refresh_courses()

    def _duplicate_course(self) -> None:
        term = self._selected_term()
        course = self._selected_course()
        if term is None or course is None:
            return
        dialog = CourseEditDialog(course, parent=self)
        dialog.setWindowTitle("复制课程")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        term.add_course(CourseEntry.create(**dialog.values()))
        self._refresh_courses()

    def _import_courses(self) -> None:
        term = self._selected_term()
        if term is None:
            QMessageBox.information(self, "先创建学期", "创建并选中一个学期后才能导入课程。")
            return
        dialog = ScheduleImportDialog(term, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        rows = dialog.imported_rows()
        for row in rows:
            term.add_course(row.to_course(self._next_color(term)))
        self._refresh_courses()
        QMessageBox.information(
            self,
            "课程已加入",
            f"已将 {len(rows)} 门课程加入“{term.name}”。\n请点击“保存课表”完成写入。",
        )

    def _delete_course(self) -> None:
        term = self._selected_term()
        course = self._selected_course()
        if term is None or course is None:
            return
        result = QMessageBox.question(
            self,
            "删除课程",
            f"永久删除课程“{course.code}”？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            term.remove_course(course.id)
            self._refresh_courses()

    def _save(self) -> None:
        self._store.save()
        self.accept()

    def result_config(self) -> dict:
        return {
            "show_weekends": self._show_weekends.isChecked(),
            "time_format": self._time_format.currentData(),
            "notifications_enabled": self._notifications_enabled.isChecked(),
            "reminder_minutes": self._reminder_minutes.value(),
        }
