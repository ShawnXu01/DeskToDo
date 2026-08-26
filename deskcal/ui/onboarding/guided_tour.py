"""主界面首次使用气泡导览。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QPainter, QPainterPath, QPen, QPolygon
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

TOUR_VERSION = 1


@dataclass(frozen=True)
class TourStep:
    key: str
    title: str
    body: str
    target_key: Optional[str] = None
    skip_if_missing: bool = False


TOUR_STEPS = (
    TourStep(
        key="welcome",
        title="欢迎使用 DeskToDo",
        body="用 30 秒认识最常用的操作。你可以随时跳过，也能从系统托盘重新查看。",
    ),
    TourStep(
        key="calendar",
        title="直接在日期上安排任务",
        body="右键日期新建任务；勾选即可完成，双击任务可以再次编辑。",
        target_key="calendar_day",
    ),
    TourStep(
        key="widgets",
        title="日常信息都在左上方",
        body="天气、待办、倒计时和进度会显示在这里；内容较多时可以滚动。",
        target_key="widgets",
    ),
    TourStep(
        key="schedule",
        title="课表在左下方",
        body="点击课程查看完整课表；点击学期名称可以切换学期、管理课程或快捷导入。",
        target_key="schedule",
        skip_if_missing=True,
    ),
    TourStep(
        key="tray",
        title="更多操作在系统托盘",
        body="右键任务栏通知区域中的 DeskToDo 图标，可以打开设置、解锁布局、临时隐藏或退出。",
    ),
    TourStep(
        key="finish",
        title="准备好了",
        body="现在可以试着右键一个日期，添加你的第一条任务。",
        target_key="calendar_day",
    ),
)


class TourBubble(QFrame):
    previousRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    skipRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tourBubble")
        self.setFixedWidth(330)
        self.setStyleSheet(
            "QFrame#tourBubble { background-color: #272727; border: 1px solid #545454; border-radius: 12px; }"
            "QLabel { color: #f4f4f4; background: transparent; }"
            "QPushButton { background-color: #3a3a3a; color: #ffffff; border: none; "
            "border-radius: 4px; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #4a4a4a; }"
            "QPushButton:disabled { color: #777777; background-color: #303030; }"
            "QPushButton#tourNext { background-color: #123d70; }"
            "QPushButton#tourNext:hover { background-color: #194f8e; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self._title = QLabel()
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._body = QLabel()
        self._body.setStyleSheet("color: #d3d3d3; font-size: 12px;")
        self._body.setWordWrap(True)
        layout.addWidget(self._body)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        skip = QPushButton("跳过")
        skip.clicked.connect(self.skipRequested.emit)
        footer.addWidget(skip)
        self._progress = QLabel()
        self._progress.setStyleSheet("color: #a8a8a8; font-size: 11px;")
        footer.addWidget(self._progress)
        footer.addStretch(1)
        self._previous = QPushButton("上一步")
        self._previous.clicked.connect(self.previousRequested.emit)
        footer.addWidget(self._previous)
        self._next = QPushButton("下一步")
        self._next.setObjectName("tourNext")
        self._next.clicked.connect(self.nextRequested.emit)
        footer.addWidget(self._next)
        layout.addLayout(footer)

    def set_step(self, step: TourStep, position: int, total: int) -> None:
        self._title.setText(step.title)
        self._body.setText(step.body)
        self._progress.setText(f"{position} / {total}")
        self._previous.setEnabled(position > 1)
        self._next.setText("完成" if position == total else "下一步")
        self.adjustSize()


class GuidedTourOverlay(QWidget):
    dismissed = pyqtSignal()
    stepChanged = pyqtSignal(str)

    def __init__(self, target_resolver: Callable[[str], Optional[QRect]], parent=None):
        super().__init__(parent)
        self._target_resolver = target_resolver
        self._available_steps: list[TourStep] = []
        self._step_index = 0
        self._target_rect: Optional[QRect] = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        self._bubble = TourBubble(self)
        self._bubble.previousRequested.connect(self._previous)
        self._bubble.nextRequested.connect(self._next)
        self._bubble.skipRequested.connect(self._dismiss)

    def start(self) -> None:
        self._available_steps = [
            step
            for step in TOUR_STEPS
            if not (
                step.skip_if_missing
                and step.target_key is not None
                and self._target_resolver(step.target_key) is None
            )
        ]
        self._step_index = 0
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._show_current_step()

    def _show_current_step(self) -> None:
        step = self._available_steps[self._step_index]
        self._target_rect = self._target_resolver(step.target_key) if step.target_key else None
        self._bubble.set_step(step, self._step_index + 1, len(self._available_steps))
        self._place_bubble()
        self.stepChanged.emit(step.key)
        self.update()

    def _next(self) -> None:
        if self._step_index >= len(self._available_steps) - 1:
            self._dismiss()
            return
        self._step_index += 1
        self._show_current_step()

    def _previous(self) -> None:
        if self._step_index <= 0:
            return
        self._step_index -= 1
        self._show_current_step()

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()

    def _place_bubble(self) -> None:
        bubble_size = self._bubble.sizeHint()
        margin = 16
        gap = 18
        if self._target_rect is None:
            x = (self.width() - bubble_size.width()) // 2
            y = (self.height() - bubble_size.height()) // 2
        else:
            target = self._target_rect
            candidates = (
                (target.right() + gap, target.center().y() - bubble_size.height() // 2),
                (target.left() - gap - bubble_size.width(), target.center().y() - bubble_size.height() // 2),
                (target.center().x() - bubble_size.width() // 2, target.bottom() + gap),
                (target.center().x() - bubble_size.width() // 2, target.top() - gap - bubble_size.height()),
            )
            x, y = next(
                (
                    (candidate_x, candidate_y)
                    for candidate_x, candidate_y in candidates
                    if margin <= candidate_x
                    and candidate_x + bubble_size.width() <= self.width() - margin
                    and margin <= candidate_y
                    and candidate_y + bubble_size.height() <= self.height() - margin
                ),
                candidates[0],
            )
            x = max(margin, min(x, self.width() - bubble_size.width() - margin))
            y = max(margin, min(y, self.height() - bubble_size.height() - margin))
        self._bubble.setGeometry(QRect(x, y, bubble_size.width(), bubble_size.height()))
        self._bubble.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isVisible() and self._available_steps:
            step = self._available_steps[self._step_index]
            self._target_rect = self._target_resolver(step.target_key) if step.target_key else None
            self._place_bubble()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dim_path = QPainterPath()
        dim_path.addRect(QRectF(self.rect()))

        if self._target_rect is not None:
            spotlight = self._target_rect.adjusted(-6, -6, 6, 6).intersected(self.rect())
            spotlight_path = QPainterPath()
            spotlight_path.addRoundedRect(QRectF(spotlight), 8, 8)
            dim_path = dim_path.subtracted(spotlight_path)
            painter.fillPath(dim_path, QColor(0, 0, 0, 150))
            painter.setPen(QPen(QColor("#8bbcf0"), 2))
            painter.drawRoundedRect(QRectF(spotlight), 8, 8)
            self._paint_arrow(painter, spotlight)
        else:
            painter.fillPath(dim_path, QColor(0, 0, 0, 150))
        painter.end()

    def _paint_arrow(self, painter: QPainter, target: QRect) -> None:
        bubble = self._bubble.geometry()
        color = QColor("#272727")
        if bubble.left() >= target.right():
            center = max(bubble.top() + 18, min(target.center().y(), bubble.bottom() - 18))
            points = QPolygon([
                bubble.topLeft() + QPoint(0, center - bubble.top() - 9),
                bubble.topLeft() + QPoint(-10, center - bubble.top()),
                bubble.topLeft() + QPoint(0, center - bubble.top() + 9),
            ])
        elif bubble.right() <= target.left():
            center = max(bubble.top() + 18, min(target.center().y(), bubble.bottom() - 18))
            points = QPolygon([
                QPoint(bubble.right(), center - 9),
                QPoint(bubble.right() + 10, center),
                QPoint(bubble.right(), center + 9),
            ])
        elif bubble.top() >= target.bottom():
            center = max(bubble.left() + 18, min(target.center().x(), bubble.right() - 18))
            points = QPolygon([
                QPoint(center - 9, bubble.top()),
                QPoint(center, bubble.top() - 10),
                QPoint(center + 9, bubble.top()),
            ])
        else:
            center = max(bubble.left() + 18, min(target.center().x(), bubble.right() - 18))
            points = QPolygon([
                QPoint(center - 9, bubble.bottom()),
                QPoint(center, bubble.bottom() + 10),
                QPoint(center + 9, bubble.bottom()),
            ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(points)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self._next()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Left:
            self._previous()
            event.accept()
            return
        super().keyPressEvent(event)
