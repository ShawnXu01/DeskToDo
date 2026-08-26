"""从 AI 生成的 CSV 预览并导入课程。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from deskcal.core.schedule_import import (
    AI_SCHEDULE_PROMPT,
    ScheduleImportError,
    ScheduleImportRow,
    analyze_import_rows,
    parse_schedule_csv,
)
from deskcal.core.schedule_models import Term
from deskcal.utils.icons import app_icon

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class ScheduleImportDialog(QDialog):
    def __init__(self, term: Term, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 课表图片快捷导入")
        self.setWindowIcon(app_icon())
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.resize(860, 650)
        self.setMinimumSize(720, 560)
        self._rows: list[ScheduleImportRow] = []
        self._term = term

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"导入到：{term.name}")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "1. 复制提示词并连同课表截图发给支持图片识别的 AI。\n"
            "2. 让 AI 生成 CSV 文件，然后在下方选择该文件。\n"
            "3. 检查预览无误后确认导入；现有课程不会被覆盖。"
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        prompt_row = QHBoxLayout()
        prompt_row.addWidget(QLabel("AI 提示词"))
        prompt_row.addStretch(1)
        copy_prompt = QPushButton("复制提示词")
        copy_prompt.clicked.connect(lambda: self._copy_prompt(copy_prompt))
        prompt_row.addWidget(copy_prompt)
        layout.addLayout(prompt_row)

        prompt = QPlainTextEdit(AI_SCHEDULE_PROMPT)
        prompt.setReadOnly(True)
        prompt.setFixedHeight(155)
        prompt.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(prompt)

        file_row = QHBoxLayout()
        self._file_path = QLineEdit()
        self._file_path.setReadOnly(True)
        self._file_path.setPlaceholderText("请选择 AI 生成的 schedule_import.csv")
        choose_file = QPushButton("选择 CSV")
        choose_file.clicked.connect(self._choose_file)
        file_row.addWidget(self._file_path, 1)
        file_row.addWidget(choose_file)
        layout.addLayout(file_row)

        self._status = QLabel("尚未选择文件。")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._preview = QTableWidget(0, 7)
        self._preview.setHorizontalHeaderLabels(["课程", "课程名称", "上课日", "时间", "地点", "教师", "检查"])
        self._preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._preview.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._preview.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._preview.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._preview.verticalHeader().setVisible(False)
        self._preview.setWordWrap(False)
        self._preview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._preview, 1)

        actions = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        self._import = QPushButton("确认导入")
        self._import.setEnabled(False)
        self._import.clicked.connect(self.accept)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(self._import)
        layout.addLayout(actions)

    def imported_rows(self) -> list[ScheduleImportRow]:
        return list(self._rows)

    def _copy_prompt(self, button: QPushButton) -> None:
        QGuiApplication.clipboard().setText(AI_SCHEDULE_PROMPT)
        button.setText("已复制")

    def _choose_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择课表 CSV",
            "",
            "CSV 文件 (*.csv)",
        )
        if not file_name:
            return
        self._file_path.setText(file_name)
        try:
            rows = parse_schedule_csv(Path(file_name))
        except ScheduleImportError as exc:
            self._rows = []
            self._preview.setRowCount(0)
            visible_errors = exc.errors[:8]
            suffix = f"\n另有 {len(exc.errors) - 8} 个错误。" if len(exc.errors) > 8 else ""
            self._status.setText("无法导入：\n" + "\n".join(visible_errors) + suffix)
            self._status.setStyleSheet("color: #ff9b91;")
            self._import.setEnabled(False)
            self._import.setText("确认导入")
            return

        self._rows = rows
        issues = analyze_import_rows(rows, self._term.courses)
        self._populate_preview(issues)
        scheduled = sum(not row.is_unscheduled for row in rows)
        unscheduled = len(rows) - scheduled
        summary = f"已识别 {len(rows)} 门课程：{scheduled} 门固定时间课程"
        if unscheduled:
            summary += f"，{unscheduled} 门无固定时间课程"
        issue_count = sum(bool(row_issues) for row_issues in issues)
        if issue_count:
            summary += f"；{issue_count} 行需要留意"
        self._status.setText(summary + "。请核对后导入。")
        self._status.setStyleSheet("color: #e6b85c;" if issue_count else "color: #9ed6a8;")
        self._import.setEnabled(True)
        self._import.setText(f"导入 {len(rows)} 门课程")

    def _populate_preview(self, issues: list[list[str]]) -> None:
        self._preview.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            if row.is_unscheduled:
                days_text = "—"
                time_text = "无固定时间"
            else:
                days_text = "/".join(DAY_LABELS[day - 1] for day in row.weekdays)
                time_text = f"{row.start_time.strftime('%H:%M')}–{row.end_time.strftime('%H:%M')}"
            values = (
                row.course_code,
                row.course_title or "—",
                days_text,
                time_text,
                row.location or "—",
                row.instructor or "—",
                "；".join(issues[row_index]) if issues[row_index] else "可以导入",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 6:
                    item.setForeground(QColor("#e6b85c" if issues[row_index] else "#9ed6a8"))
                self._preview.setItem(row_index, column, item)
