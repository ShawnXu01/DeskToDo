"""完整课表窗口：大周视图、Term 切换和课程详情。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.schedule_models import CourseEntry, Term
from deskcal.core.schedule_storage import ScheduleStore
from deskcal.ui.schedule.course_resource import open_course_resource
from deskcal.ui.schedule.schedule_grid import ScheduleGrid
from deskcal.ui.schedule.schedule_settings import CourseEditDialog, SCHEDULE_QSS, ScheduleSettingsDialog, format_weekdays
from deskcal.ui.style_utils import make_scroll_area_transparent
from deskcal.utils.icons import app_icon


class ScheduleWindow(QWidget):
    dataChanged = pyqtSignal()
    configChanged = pyqtSignal(dict)

    def __init__(self, config: dict, selected_course_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DeskToDo — 课表")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Window)
        self.setStyleSheet(SCHEDULE_QSS)
        self.resize(1000, 680)
        self.setMinimumSize(760, 520)
        self._config = dict(config)
        self._store = ScheduleStore()
        self._store.load()
        self._selected_course_id = selected_course_id

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        toolbar = QHBoxLayout()
        self._term_combo = QComboBox()
        self._term_combo.setMinimumWidth(180)
        self._term_combo.currentIndexChanged.connect(self._on_term_changed)
        toolbar.addWidget(self._term_combo)
        today_btn = QPushButton("今天")
        today_btn.clicked.connect(self._go_today)
        toolbar.addWidget(today_btn)
        self._days_combo = QComboBox()
        self._days_combo.addItem("工作日", False)
        self._days_combo.addItem("全周", True)
        self._days_combo.setCurrentIndex(1 if self._config.get("show_weekends", False) else 0)
        self._days_combo.currentIndexChanged.connect(self._on_days_changed)
        toolbar.addWidget(self._days_combo)
        manage_btn = QPushButton("管理课程")
        manage_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(manage_btn)
        toolbar.addStretch(1)
        outer.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._grid = ScheduleGrid(
            compact=False,
            show_weekends=self._config.get("show_weekends", False),
            use_24_hour=self._config.get("time_format", "12h") == "24h",
        )
        self._grid.courseClicked.connect(self._select_course)
        scroll = QScrollArea()
        scroll.setWidget(self._grid)
        scroll.setWidgetResizable(True)
        make_scroll_area_transparent(scroll)
        splitter.addWidget(scroll)

        details = QFrame()
        details.setMinimumWidth(240)
        details.setMaximumWidth(340)
        detail_layout = QVBoxLayout(details)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(10)
        self._course_code = QLabel("选择一门课程")
        self._course_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._course_code.setFixedHeight(86)
        self._course_code.setStyleSheet("font-size: 22px; font-weight: bold; background: #242424; border-radius: 8px;")
        detail_layout.addWidget(self._course_code)
        self._course_title = QLabel("从课表中选择课程以查看详情")
        self._course_title.setWordWrap(True)
        self._course_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        detail_layout.addWidget(self._course_title)
        self._course_days = QLabel()
        self._course_time = QLabel()
        self._course_location = QLabel()
        self._course_instructor = QLabel()
        self._course_notes = QLabel()
        self._course_notes.setWordWrap(True)
        for label in (
            self._course_days,
            self._course_time,
            self._course_location,
            self._course_instructor,
            self._course_notes,
        ):
            label.setWordWrap(True)
            label.setStyleSheet("color: #d6d6d6;")
            detail_layout.addWidget(label)
        detail_layout.addStretch(1)
        self._edit_btn = QPushButton("编辑课程")
        self._edit_btn.clicked.connect(self._edit_selected_course)
        detail_layout.addWidget(self._edit_btn)
        self._duplicate_btn = QPushButton("复制课程")
        self._duplicate_btn.clicked.connect(self._duplicate_selected_course)
        detail_layout.addWidget(self._duplicate_btn)
        self._resource_btn = QPushButton("打开课程资料")
        self._resource_btn.clicked.connect(self._open_selected_course_resource)
        detail_layout.addWidget(self._resource_btn)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, 1)

        self._refresh_terms()

    def _active_term(self) -> Optional[Term]:
        return self._store.get_active_term()

    def _selected_course(self) -> Optional[CourseEntry]:
        term = self._active_term()
        return term.get_course(self._selected_course_id) if term and self._selected_course_id else None

    def _refresh_terms(self) -> None:
        self._term_combo.blockSignals(True)
        self._term_combo.clear()
        terms = sorted(self._store.terms.values(), key=lambda term: (term.archived, term.start_date))
        target = -1
        for index, term in enumerate(terms):
            label = f"{term.name} · 已归档" if term.archived else term.name
            self._term_combo.addItem(label, term.id)
            if term.id == self._store.active_term_id:
                target = index
        self._term_combo.blockSignals(False)
        if target < 0 and terms:
            target = 0
        self._term_combo.setCurrentIndex(target)
        if target >= 0:
            self._store.active_term_id = self._term_combo.currentData()
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        term = self._active_term()
        if term is None or (self._selected_course_id and term.get_course(self._selected_course_id) is None):
            self._selected_course_id = None
        self._grid.set_term(term)
        self._grid.set_selected_course(self._selected_course_id)
        self._update_details()

    def _on_term_changed(self, index: int) -> None:
        term_id = self._term_combo.itemData(index)
        if not term_id:
            return
        self._store.set_active_term(term_id)
        self._store.save()
        self._selected_course_id = None
        self._refresh_grid()
        self.dataChanged.emit()

    def _go_today(self) -> None:
        self._store.active_term_id = None
        term = self._store.choose_default_term(date.today())
        if term is None:
            return
        self._store.save()
        index = self._term_combo.findData(term.id)
        self._term_combo.setCurrentIndex(index)

    def _on_days_changed(self, index: int) -> None:
        show_weekends = bool(self._days_combo.itemData(index))
        self._config["show_weekends"] = show_weekends
        self._grid.set_show_weekends(show_weekends)
        self.configChanged.emit(dict(self._config))

    def _select_course(self, course_id: Optional[str]) -> None:
        self._selected_course_id = course_id
        self._grid.set_selected_course(course_id)
        self._update_details()

    def _update_details(self) -> None:
        course = self._selected_course()
        enabled = course is not None
        self._edit_btn.setEnabled(enabled)
        self._duplicate_btn.setEnabled(enabled)
        self._resource_btn.setEnabled(bool(course and course.course_resource))
        if course is None:
            self._course_code.setText("选择一门课程")
            self._course_code.setStyleSheet("font-size: 18px; font-weight: bold; background: #242424; border-radius: 8px;")
            self._course_title.setText("从课表中选择课程以查看详情")
            for label in (self._course_days, self._course_time, self._course_location, self._course_instructor, self._course_notes):
                label.clear()
            return
        self._course_code.setText(course.code)
        self._course_code.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: #102a43; background: {course.color}; border-radius: 8px;"
        )
        self._course_title.setText(course.title or "未填写课程全名")
        self._course_days.setText(f"上课日\n{format_weekdays(course.weekdays) or '无固定日期'}")
        time_text = (
            f"{course.start_time.strftime('%I:%M %p').lstrip('0')}–"
            f"{course.end_time.strftime('%I:%M %p').lstrip('0')}"
            if course.start_time and course.end_time
            else "无固定时间"
        )
        self._course_time.setText(f"时间\n{time_text}")
        self._course_location.setText(f"地点\n{course.location or '未填写'}")
        self._course_instructor.setText(f"教师\n{course.instructor or '未填写'}")
        self._course_notes.setText(f"备注\n{course.notes}" if course.notes else "")

    def _open_selected_course_resource(self) -> None:
        course = self._selected_course()
        if course is None or not course.course_resource:
            return
        opened, error = open_course_resource(course.course_resource)
        if not opened:
            QMessageBox.warning(self, "无法打开课程资料", error)

    def _edit_selected_course(self) -> None:
        term = self._active_term()
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
        self._store.save()
        self._refresh_grid()
        self.dataChanged.emit()

    def _duplicate_selected_course(self) -> None:
        term = self._active_term()
        course = self._selected_course()
        if term is None or course is None:
            return
        dialog = CourseEditDialog(course, parent=self)
        dialog.setWindowTitle("复制课程")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        duplicate = CourseEntry.create(**dialog.values())
        term.add_course(duplicate)
        self._store.save()
        self._selected_course_id = duplicate.id
        self._refresh_grid()
        self.dataChanged.emit()

    def _open_settings(self) -> None:
        dialog = ScheduleSettingsDialog(self._config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._config = dialog.result_config()
        self._store.load()
        self._days_combo.setCurrentIndex(1 if self._config.get("show_weekends", False) else 0)
        self._grid.set_use_24_hour(self._config.get("time_format", "12h") == "24h")
        self._refresh_terms()
        self.configChanged.emit(dict(self._config))
        self.dataChanged.emit()
