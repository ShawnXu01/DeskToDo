"""桌面层窗口：三栏组合（组件区[Phase 4 实现] + 待办收纳侧栏 + 日历主体），
外加无边框/贴底层/半透明背景，以及解锁=可拖动缩放、锁定=恢复日历交互 的窗口行为。

解锁状态下用一个盖住全窗口的半透明"调整模式"层挡住所有点击，由它统一处理拖动/缩放，
日历和侧栏本身不需要任何"是否可交互"开关，天然避免了拖动手势和右键建任务的区域冲突。
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from deskcal.core.storage import TaskStore, load_window_geometry, save_window_geometry
from deskcal.core.sync.gist_provider import GistSyncProvider
from deskcal.services.sync_manager import SyncManager
from deskcal.ui.config_panel.config_window import ConfigWindow
from deskcal.ui.desktop_overlay.calendar_grid import COLS, ROWS, CalendarGrid
from deskcal.ui.desktop_overlay.sidebar_todo import SidebarTodo
from deskcal.ui.desktop_overlay.widgets.registry import WIDGET_DEFINITIONS, WidgetConfigStore
from deskcal.ui.style_utils import make_scroll_area_transparent
from deskcal.utils import crypto

PANEL_RADIUS = 16
PANEL_COLOR = QColor(20, 20, 20, 230)
BLUR_TINT_COLOR = QColor(20, 20, 20, 140)
BLUR_RADIUS = 18

# 整窗统一走 paintEvent 画圆角背板（见 OverlayWindow.paintEvent），子控件一律透明，
# 这里只保留按钮/滚动条这些“样式无法直接画在背板上”的控件外观。
WIDGET_QSS = """
QPushButton {
    background-color: rgba(255, 255, 255, 30);
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}
QPushButton:hover { background-color: rgba(255, 255, 255, 60); }
QPushButton:checked { background-color: rgba(255, 255, 255, 90); }
QScrollBar:vertical {
    width: 4px;
    background: transparent;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 80);
    border-radius: 2px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

DEFAULT_WIDGET_AREA_WIDTH = 200
DEFAULT_SIDEBAR_WIDTH = 180
MARGIN = 8
GAP = 8
OUTER_MARGIN = MARGIN * 2
COLUMN_SPACING = GAP * 2

# 三个模块（组件区/侧栏/日历）宽度可由用户在调整模式下拖拽分割线改变，这两个是下限，
# 防止某个模块被拖到几乎看不见。
MIN_WIDGET_AREA_WIDTH = 120
MIN_SIDEBAR_WIDTH = 120

# 最小尺寸不是拍脑袋定的数字，而是反推"日历格子至少能显示日期数字+一条任务"所需的空间
MIN_CELL_WIDTH = 60
MIN_CELL_HEIGHT = 48
CALENDAR_CHROME_HEIGHT = 60  # 年月标题行 + 星期表头行的估算高度

MIN_CALENDAR_WIDTH = MIN_CELL_WIDTH * COLS
MIN_CALENDAR_HEIGHT = CALENDAR_CHROME_HEIGHT + MIN_CELL_HEIGHT * ROWS

MIN_WINDOW_WIDTH = MIN_WIDGET_AREA_WIDTH + MIN_SIDEBAR_WIDTH + MIN_CALENDAR_WIDTH + OUTER_MARGIN + COLUMN_SPACING
MIN_WINDOW_HEIGHT = MIN_CALENDAR_HEIGHT + OUTER_MARGIN

RESIZE_MARGIN = 8
DIVIDER_HIT_MARGIN = 6
DIVIDER_LINE_COLOR = QColor(255, 255, 255, 160)


class AdjustModeOverlay(QWidget):
    """解锁状态下盖住整个窗口的调整层：拖动空白处移动窗口，拖动边缘缩放。"""

    def __init__(self, target: "OverlayWindow", parent=None):
        super().__init__(parent)
        self._target = target
        self._drag_start_mouse = None
        self._drag_start_geometry = None
        self._resize_edges: set[str] = set()
        self._backdrop: Optional[QPixmap] = None
        self._dragging_divider: Optional[int] = None
        self._divider_drag_start_x = 0
        self._divider_drag_start_widths = (0, 0)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        label = QLabel("调整模式\n拖动空白处移动窗口 · 拖动边缘缩放 · 拖动竖线调整三栏宽度 · 锁定后生效")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(label)

    def set_backdrop(self, pixmap: QPixmap) -> None:
        """截一张当前窗口内容的快照、做高斯模糊，当作调整模式的磨砂玻璃底图。"""
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(pixmap)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(BLUR_RADIUS)
        item.setGraphicsEffect(blur)
        scene.addItem(item)

        blurred = QPixmap(pixmap.size())
        blurred.fill(Qt.GlobalColor.transparent)
        painter = QPainter(blurred)
        scene.render(painter)
        painter.end()

        self._backdrop = blurred
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._backdrop is not None:
            painter.drawPixmap(self.rect(), self._backdrop)
        painter.fillRect(self.rect(), BLUR_TINT_COLOR)

        pen = QPen(DIVIDER_LINE_COLOR)
        pen.setWidth(2)
        painter.setPen(pen)
        for divider_x in self._target.divider_x_positions():
            painter.drawLine(divider_x, 0, divider_x, self.height())

        painter.end()
        super().paintEvent(event)

    def _divider_at(self, pos) -> Optional[int]:
        for index, divider_x in enumerate(self._target.divider_x_positions(), start=1):
            if abs(pos.x() - divider_x) <= DIVIDER_HIT_MARGIN:
                return index
        return None

    def _edges_at(self, pos) -> set[str]:
        edges: set[str] = set()
        if pos.x() <= RESIZE_MARGIN:
            edges.add("left")
        elif pos.x() >= self.width() - RESIZE_MARGIN:
            edges.add("right")
        if pos.y() <= RESIZE_MARGIN:
            edges.add("top")
        elif pos.y() >= self.height() - RESIZE_MARGIN:
            edges.add("bottom")
        return edges

    def _update_cursor(self, edges: set[str]) -> None:
        diagonal_nw_se = {"left", "top"}, {"right", "bottom"}
        diagonal_ne_sw = {"right", "top"}, {"left", "bottom"}
        if edges in diagonal_nw_se:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in diagonal_ne_sw:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif "left" in edges or "right" in edges:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif "top" in edges or "bottom" in edges:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event) -> None:
        pos = event.position().toPoint()
        divider = self._divider_at(pos)
        if divider is not None:
            self._dragging_divider = divider
            self._divider_drag_start_x = event.globalPosition().toPoint().x()
            self._divider_drag_start_widths = self._target.current_column_widths()
            return

        self._drag_start_mouse = event.globalPosition().toPoint()
        self._drag_start_geometry = self._target.geometry()
        self._resize_edges = self._edges_at(pos)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_divider is not None:
            delta_x = event.globalPosition().toPoint().x() - self._divider_drag_start_x
            start_widget_width, start_sidebar_width = self._divider_drag_start_widths
            if self._dragging_divider == 1:
                self._target.set_widget_area_width(start_widget_width + delta_x)
            else:
                self._target.set_sidebar_width(start_sidebar_width + delta_x)
            self.update()
            return

        if self._drag_start_mouse is None:
            divider = self._divider_at(event.position().toPoint())
            if divider is not None:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self._update_cursor(self._edges_at(event.position().toPoint()))
            return

        delta = event.globalPosition().toPoint() - self._drag_start_mouse
        geo = self._drag_start_geometry

        if self._resize_edges:
            new_rect = QRect(geo)
            if "left" in self._resize_edges:
                new_rect.setLeft(geo.left() + delta.x())
            if "right" in self._resize_edges:
                new_rect.setRight(geo.right() + delta.x())
            if "top" in self._resize_edges:
                new_rect.setTop(geo.top() + delta.y())
            if "bottom" in self._resize_edges:
                new_rect.setBottom(geo.bottom() + delta.y())

            min_width = self._target.minimumWidth()
            min_height = self._target.minimumHeight()
            if new_rect.width() < min_width:
                if "left" in self._resize_edges:
                    new_rect.setLeft(new_rect.right() - min_width)
                else:
                    new_rect.setRight(new_rect.left() + min_width)
            if new_rect.height() < min_height:
                if "top" in self._resize_edges:
                    new_rect.setTop(new_rect.bottom() - min_height)
                else:
                    new_rect.setBottom(new_rect.top() + min_height)

            self._target.setGeometry(new_rect)
        else:
            self._target.move(geo.topLeft() + delta)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging_divider is not None:
            self._dragging_divider = None
            return
        self._drag_start_mouse = None
        self._drag_start_geometry = None
        self._resize_edges = set()
        self._update_cursor(self._edges_at(event.position().toPoint()))


class OverlayWindow(QWidget):
    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)

        self.setWindowTitle("DeskCal")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setStyleSheet(WIDGET_QSS)
        self._widget_area_width = DEFAULT_WIDGET_AREA_WIDTH
        self._sidebar_width = DEFAULT_SIDEBAR_WIDTH
        self._restore_geometry()

        self._widget_store = WidgetConfigStore()
        self._widget_store.load()
        self._config_window: Optional[ConfigWindow] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(GAP)

        self._widget_area_container = QWidget()
        self._widget_area_layout = QVBoxLayout(self._widget_area_container)
        self._widget_area_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_area_layout.setSpacing(4)
        self._widget_area_layout.addStretch(1)

        self._widget_area_scroll = QScrollArea()
        self._widget_area_scroll.setWidget(self._widget_area_container)
        self._widget_area_scroll.setWidgetResizable(True)
        self._widget_area_scroll.setFixedWidth(self._widget_area_width)
        self._widget_area_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._widget_area_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        make_scroll_area_transparent(self._widget_area_scroll)
        layout.addWidget(self._widget_area_scroll)

        self._sidebar = SidebarTodo(store)
        self._sidebar.setFixedWidth(self._sidebar_width)
        layout.addWidget(self._sidebar)

        self._calendar = CalendarGrid(store)
        layout.addWidget(self._calendar, 1)

        self.render_widgets()

        self._sync_manager: Optional[SyncManager] = None
        gist_token = crypto.load_gist_token()
        if gist_token:
            provider = GistSyncProvider(gist_token)
            self._sync_manager = SyncManager(store, provider, parent=self)
            self._sync_manager.data_changed.connect(self._on_sync_data_changed)

        self._locked = True
        self._adjust_overlay = AdjustModeOverlay(self, parent=self)
        self._adjust_overlay.setGeometry(self.rect())
        self._adjust_overlay.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), PANEL_RADIUS, PANEL_RADIUS)
        painter.fillPath(path, PANEL_COLOR)
        painter.end()
        super().paintEvent(event)

    def _restore_geometry(self) -> None:
        saved = load_window_geometry()
        if saved is not None:
            self._widget_area_width = max(saved.get("widget_area_width", DEFAULT_WIDGET_AREA_WIDTH), MIN_WIDGET_AREA_WIDTH)
            self._sidebar_width = max(saved.get("sidebar_width", DEFAULT_SIDEBAR_WIDTH), MIN_SIDEBAR_WIDTH)

            width = max(saved["width"], MIN_WINDOW_WIDTH)
            height = max(saved["height"], MIN_WINDOW_HEIGHT)
            candidate = QRect(saved["x"], saved["y"], width, height)
            on_screen = any(
                screen.availableGeometry().intersects(candidate) for screen in QGuiApplication.screens()
            )
            if on_screen:
                self.setGeometry(candidate)
                return
        self.resize(1100, 700)

    def persist_geometry(self) -> None:
        geo = self.geometry()
        save_window_geometry(geo.x(), geo.y(), geo.width(), geo.height(), self._widget_area_width, self._sidebar_width)

    def closeEvent(self, event) -> None:
        self.persist_geometry()
        super().closeEvent(event)

    def current_column_widths(self) -> tuple[int, int]:
        return self._widget_area_width, self._sidebar_width

    def divider_x_positions(self) -> tuple[int, int]:
        divider1 = MARGIN + self._widget_area_width + GAP // 2
        divider2 = MARGIN + self._widget_area_width + GAP + self._sidebar_width + GAP // 2
        return divider1, divider2

    def set_widget_area_width(self, width: int) -> None:
        max_width = self.width() - MARGIN * 2 - GAP * 2 - self._sidebar_width - MIN_CALENDAR_WIDTH
        self._widget_area_width = max(MIN_WIDGET_AREA_WIDTH, min(width, max_width))
        self._widget_area_scroll.setFixedWidth(self._widget_area_width)

    def set_sidebar_width(self, width: int) -> None:
        max_width = self.width() - MARGIN * 2 - GAP * 2 - self._widget_area_width - MIN_CALENDAR_WIDTH
        self._sidebar_width = max(MIN_SIDEBAR_WIDTH, min(width, max_width))
        self._sidebar.setFixedWidth(self._sidebar_width)

    def _on_sync_data_changed(self) -> None:
        self._calendar.render()
        self._sidebar.render()

    def render_widgets(self) -> None:
        while self._widget_area_layout.count() > 1:
            item = self._widget_area_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for instance in self._widget_store.enabled_items():
            definition = WIDGET_DEFINITIONS[instance.type_id]
            widget = definition.widget_class(instance.config)
            self._widget_area_layout.insertWidget(self._widget_area_layout.count() - 1, widget)

    def open_config_panel(self) -> None:
        if self._config_window is None:
            self._config_window = ConfigWindow(
                self._widget_store,
                on_widgets_changed=self.render_widgets,
                sync_manager=self._sync_manager,
            )
        self._config_window.show()
        self._config_window.raise_()
        self._config_window.activateWindow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_widget_area_scroll"):
            return  # 构造阶段 _restore_geometry() 里的 resize() 也会触发这个事件，那时子控件还没建好
        self._adjust_overlay.setGeometry(self.rect())
        # 整窗变窄时（拖边缘缩放），重新夹一下当前列宽，避免组件区/侧栏的固定宽度
        # 加起来超过新窗口能给的空间。
        self.set_widget_area_width(self._widget_area_width)
        self.set_sidebar_width(self._sidebar_width)

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        if locked:
            self._adjust_overlay.hide()
            self.persist_geometry()
        else:
            self._adjust_overlay.set_backdrop(self.grab())
            self._adjust_overlay.setGeometry(self.rect())
            self._adjust_overlay.show()
            self._adjust_overlay.raise_()

    def is_locked(self) -> bool:
        return self._locked
