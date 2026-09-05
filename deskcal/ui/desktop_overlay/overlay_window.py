"""桌面层窗口：左侧上下分区（滚动组件区 + 课表）与右侧日历主体，
外加无边框/贴底层/半透明背景，以及解锁=可拖动缩放、锁定=恢复日历交互 的窗口行为。

解锁状态下用一个盖住全窗口的半透明"调整模式"层挡住所有点击，由它统一处理拖动/缩放，
日历和内容区本身不需要任何"是否可交互"开关，天然避免了拖动手势和右键建任务的区域冲突。
"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
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

from deskcal.core.storage import (
    TaskStore,
    get_main_tour_completed_version,
    load_calendar_font_scale,
    load_appearance,
    load_window_geometry,
    mark_main_tour_completed,
    normalize_calendar_font_scale,
    save_calendar_font_scale,
    save_appearance,
    save_window_geometry,
)
from deskcal.core.sync.gist_provider import GistSyncProvider
from deskcal.services.sync_manager import SyncManager
from deskcal.ui.config_panel.config_window import ConfigWindow
from deskcal.ui.desktop_overlay.calendar_grid import COLS, ROWS, CalendarGrid
from deskcal.ui.desktop_overlay.sidebar_todo import SidebarTodo
from deskcal.ui.desktop_overlay.widgets.registry import WIDGET_DEFINITIONS, WidgetConfigStore
from deskcal.ui.onboarding.guided_tour import GuidedTourOverlay, TOUR_VERSION
from deskcal.ui.style_utils import make_scroll_area_transparent
from deskcal.utils import crypto
from deskcal.utils.monitor import compute_monitor_signature, compute_screen_signature, describe_screen

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

DEFAULT_LEFT_AREA_WIDTH = 388
DEFAULT_LEFT_TOP_RATIO = 0.58
MARGIN = 8
GAP = 8
OUTER_MARGIN = MARGIN * 2
COLUMN_SPACING = GAP

# 左侧整体宽度和上下两区高度均可在调整模式中拖动；下限保证内容仍可操作。
MIN_LEFT_AREA_WIDTH = 260
MIN_LEFT_TOP_HEIGHT = 180
MIN_SCHEDULE_HEIGHT = 260

# 最小尺寸不是拍脑袋定的数字，而是反推"日历格子至少能显示日期数字+一条任务"所需的空间
MIN_CELL_WIDTH = 60
MIN_CELL_HEIGHT = 48
CALENDAR_CHROME_HEIGHT = 60  # 年月标题行 + 星期表头行的估算高度

MIN_CALENDAR_WIDTH = MIN_CELL_WIDTH * COLS
MIN_CALENDAR_HEIGHT = CALENDAR_CHROME_HEIGHT + MIN_CELL_HEIGHT * ROWS

MIN_WINDOW_WIDTH = MIN_LEFT_AREA_WIDTH + MIN_CALENDAR_WIDTH + OUTER_MARGIN + COLUMN_SPACING
MIN_WINDOW_HEIGHT = max(MIN_CALENDAR_HEIGHT + OUTER_MARGIN, MIN_LEFT_TOP_HEIGHT + MIN_SCHEDULE_HEIGHT + GAP + OUTER_MARGIN)

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
        self._dragging_divider: Optional[str] = None
        self._divider_drag_start_mouse = None
        self._divider_drag_start_value = 0

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        label = QLabel("调整模式\n拖动空白处移动窗口 · 拖动边缘缩放 · 拖动分隔线调整区域大小 · 锁定后生效")
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
        divider_x = self._target.main_divider_x()
        painter.drawLine(divider_x, 0, divider_x, self.height())
        if self._target.has_schedule_panel():
            divider_y = self._target.left_split_y()
            painter.drawLine(0, divider_y, divider_x, divider_y)

        painter.end()
        super().paintEvent(event)

    def _divider_at(self, pos) -> Optional[str]:
        if abs(pos.x() - self._target.main_divider_x()) <= DIVIDER_HIT_MARGIN:
            return "main"
        if (
            self._target.has_schedule_panel()
            and pos.x() <= self._target.main_divider_x()
            and abs(pos.y() - self._target.left_split_y()) <= DIVIDER_HIT_MARGIN
        ):
            return "left_split"
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
            self._divider_drag_start_mouse = event.globalPosition().toPoint()
            self._divider_drag_start_value = (
                self._target.left_area_width() if divider == "main" else self._target.left_top_height()
            )
            return

        self._drag_start_mouse = event.globalPosition().toPoint()
        self._drag_start_geometry = self._target.geometry()
        self._resize_edges = self._edges_at(pos)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_divider is not None:
            delta = event.globalPosition().toPoint() - self._divider_drag_start_mouse
            if self._dragging_divider == "main":
                self._target.set_left_area_width(self._divider_drag_start_value + delta.x())
            else:
                self._target.set_left_top_height(self._divider_drag_start_value + delta.y())
            self.update()
            return

        if self._drag_start_mouse is None:
            divider = self._divider_at(event.position().toPoint())
            if divider == "main":
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif divider == "left_split":
                self.setCursor(Qt.CursorShape.SizeVerCursor)
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
            self._divider_drag_start_mouse = None
            return
        self._drag_start_mouse = None
        self._drag_start_geometry = None
        self._resize_edges = set()
        self._update_cursor(self._edges_at(event.position().toPoint()))


class OverlayWindow(QWidget):
    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)

        self.setWindowTitle("DeskToDo")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnBottomHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setStyleSheet(WIDGET_QSS)
        self._store = store
        self._left_area_width = DEFAULT_LEFT_AREA_WIDTH
        self._left_top_ratio = DEFAULT_LEFT_TOP_RATIO
        self._left_split_manual = False
        self._schedule_enabled = False
        self._calendar_screen_signature = ""
        self._calendar_screen_label = ""
        self._screen_signal_connected = False
        self._restore_geometry()

        self._panel_alpha = load_appearance().get("panel_alpha", PANEL_COLOR.alpha())

        self._widget_store = WidgetConfigStore()
        self._widget_store.load()
        self._config_window: Optional[ConfigWindow] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        layout.setSpacing(GAP)

        self._left_container = QWidget()
        self._left_container.setFixedWidth(self._left_area_width)
        left_layout = QVBoxLayout(self._left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(GAP)

        self._widget_area_container = QWidget()
        self._widget_area_layout = QVBoxLayout(self._widget_area_container)
        self._widget_area_layout.setContentsMargins(0, 0, 8, 0)
        self._widget_area_layout.setSpacing(4)
        self._widget_area_layout.addStretch(1)

        self._widget_area_scroll = QScrollArea()
        self._widget_area_scroll.setWidget(self._widget_area_container)
        self._widget_area_scroll.setWidgetResizable(True)
        self._widget_area_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._widget_area_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        make_scroll_area_transparent(self._widget_area_scroll)
        left_layout.addWidget(self._widget_area_scroll)

        self._schedule_container = QWidget()
        self._schedule_layout = QVBoxLayout(self._schedule_container)
        self._schedule_layout.setContentsMargins(0, 0, 8, 0)
        self._schedule_layout.setSpacing(0)
        self._schedule_scroll = QScrollArea()
        self._schedule_scroll.setWidget(self._schedule_container)
        self._schedule_scroll.setWidgetResizable(True)
        self._schedule_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._schedule_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._schedule_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        make_scroll_area_transparent(self._schedule_scroll)
        left_layout.addWidget(self._schedule_scroll, 1)

        layout.addWidget(self._left_container)

        self._calendar = CalendarGrid(store)
        layout.addWidget(self._calendar, 1)
        self._refresh_calendar_font_for_current_screen()

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

        self._tour_tray_hint_callback: Optional[Callable[[], None]] = None
        self._guided_tour = GuidedTourOverlay(self._guided_tour_anchor, parent=self)
        self._guided_tour.setGeometry(self.rect())
        self._guided_tour.dismissed.connect(self._mark_guided_tour_completed)
        self._guided_tour.stepChanged.connect(self._on_guided_tour_step_changed)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), PANEL_RADIUS, PANEL_RADIUS)
        panel_color = QColor(PANEL_COLOR.red(), PANEL_COLOR.green(), PANEL_COLOR.blue(), self._panel_alpha)
        painter.fillPath(path, panel_color)
        painter.end()
        super().paintEvent(event)

    def set_panel_alpha(self, alpha: int) -> None:
        self._panel_alpha = alpha
        save_appearance(panel_alpha=alpha)
        self.update()

    def _restore_geometry(self) -> None:
        self._monitor_signature = compute_monitor_signature()
        self._apply_saved_or_default_geometry()

        # 插拔显示器时签名变了就换套记忆位置；不在这里反向保存，因为此时 Windows 往往已经
        # 把窗口强制挪走，保存动作仍然只发生在 set_locked/closeEvent 里。
        app = QGuiApplication.instance()
        self._screen_change_timer = QTimer(self)
        self._screen_change_timer.setSingleShot(True)
        self._screen_change_timer.timeout.connect(self._on_monitor_signature_maybe_changed)
        app.screenAdded.connect(lambda _screen: self._screen_change_timer.start(500))
        app.screenRemoved.connect(lambda _screen: self._screen_change_timer.start(500))

    def _on_monitor_signature_maybe_changed(self) -> None:
        signature = compute_monitor_signature()
        if signature == self._monitor_signature:
            return
        self._monitor_signature = signature
        self._apply_saved_or_default_geometry()
        self._refresh_calendar_font_for_current_screen()

    def _current_screen(self):
        return QGuiApplication.screenAt(self.frameGeometry().center()) or self.screen()

    def _refresh_calendar_font_for_current_screen(self) -> None:
        if not hasattr(self, "_calendar"):
            return
        screen = self._current_screen()
        if screen is None:
            return
        signature = compute_screen_signature(screen)
        if signature == self._calendar_screen_signature:
            return
        self._calendar_screen_signature = signature
        self._calendar_screen_label = describe_screen(screen)
        scale = load_calendar_font_scale(signature)
        self._calendar.set_font_scale(scale)
        if self._config_window is not None:
            self._config_window.set_calendar_font_context(scale, self._calendar_screen_label)

    def _set_current_calendar_font_scale(self, scale: int) -> None:
        if not self._calendar_screen_signature:
            self._refresh_calendar_font_for_current_screen()
        normalized = normalize_calendar_font_scale(scale)
        save_calendar_font_scale(self._calendar_screen_signature, normalized)
        self._calendar.set_font_scale(normalized)

    def _apply_saved_or_default_geometry(self) -> None:
        saved = load_window_geometry(self._monitor_signature)
        if saved is not None:
            legacy_left_width = (
                saved.get("widget_area_width", 200) + saved.get("sidebar_width", 180) + GAP
            )
            self._left_area_width = max(saved.get("left_area_width", legacy_left_width), MIN_LEFT_AREA_WIDTH)
            ratio = saved.get("left_top_ratio", DEFAULT_LEFT_TOP_RATIO)
            self._left_top_ratio = min(0.9, max(0.1, ratio)) if isinstance(ratio, (int, float)) else DEFAULT_LEFT_TOP_RATIO
            self._left_split_manual = bool(saved.get("left_split_manual", False))

            width = max(saved["width"], MIN_WINDOW_WIDTH)
            height = max(saved["height"], MIN_WINDOW_HEIGHT)
            candidate = QRect(saved["x"], saved["y"], width, height)
            on_screen = any(
                screen.availableGeometry().intersects(candidate) for screen in QGuiApplication.screens()
            )
            if hasattr(self, "_left_container"):
                self.set_left_area_width(self._left_area_width)
                self._apply_left_split()
            if on_screen:
                self.setGeometry(candidate)
                return
        self.resize(1100, 700)

    def persist_geometry(self) -> None:
        geo = self.geometry()
        save_window_geometry(
            self._monitor_signature,
            geo.x(),
            geo.y(),
            geo.width(),
            geo.height(),
            self._left_area_width,
            round(self._left_top_ratio, 4),
            self._left_split_manual,
        )

    def closeEvent(self, event) -> None:
        self.persist_geometry()
        super().closeEvent(event)

    def left_area_width(self) -> int:
        return self._left_area_width

    def left_top_height(self) -> int:
        return self._widget_area_scroll.height()

    def main_divider_x(self) -> int:
        return MARGIN + self._left_area_width + GAP // 2

    def left_split_y(self) -> int:
        return MARGIN + self.left_top_height() + GAP // 2

    def has_schedule_panel(self) -> bool:
        return self._schedule_enabled

    def set_left_area_width(self, width: int) -> None:
        max_width = self.width() - OUTER_MARGIN - GAP - MIN_CALENDAR_WIDTH
        self._left_area_width = max(MIN_LEFT_AREA_WIDTH, min(width, max_width))
        self._left_container.setFixedWidth(self._left_area_width)

    def set_left_top_height(self, height: int) -> None:
        if not self._schedule_enabled:
            return
        available = max(1, self.height() - OUTER_MARGIN - GAP)
        top_height = max(MIN_LEFT_TOP_HEIGHT, min(height, available - MIN_SCHEDULE_HEIGHT))
        self._left_top_ratio = top_height / available
        self._left_split_manual = True
        self._apply_left_split()

    def _apply_left_split(self) -> None:
        if not hasattr(self, "_widget_area_scroll"):
            return
        self._schedule_scroll.setVisible(self._schedule_enabled)
        if not self._schedule_enabled:
            self._schedule_container.setMinimumHeight(0)
            self._widget_area_scroll.setMinimumHeight(0)
            self._widget_area_scroll.setMaximumHeight(16777215)
            return
        available = max(1, self.height() - OUTER_MARGIN - GAP)
        self._schedule_container.setMinimumHeight(0)
        self._schedule_layout.activate()
        desired_schedule_height = max(MIN_SCHEDULE_HEIGHT, self._schedule_container.sizeHint().height())
        self._schedule_container.setMinimumHeight(desired_schedule_height)
        if self._left_split_manual:
            top_height = round(available * self._left_top_ratio)
        else:
            top_height = available - desired_schedule_height
        top_height = max(MIN_LEFT_TOP_HEIGHT, min(top_height, available - MIN_SCHEDULE_HEIGHT))
        self._left_top_ratio = top_height / available
        self._widget_area_scroll.setFixedHeight(top_height)

    def _on_sync_data_changed(self) -> None:
        self._calendar.render()
        if self._sidebar is not None:
            self._sidebar.render()

    def render_widgets(self) -> None:
        while self._widget_area_layout.count() > 1:
            item = self._widget_area_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        while self._schedule_layout.count():
            item = self._schedule_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._sidebar = None
        self._schedule_enabled = False
        for instance in self._widget_store.enabled_items():
            if instance.type_id == "floating_todo":
                self._sidebar = SidebarTodo(self._store)
                self._widget_area_layout.insertWidget(self._widget_area_layout.count() - 1, self._sidebar)
                continue
            definition = WIDGET_DEFINITIONS[instance.type_id]
            if definition.widget_class is None:
                continue
            widget = definition.widget_class(instance.config)
            if instance.type_id == "schedule":
                self._schedule_layout.addWidget(widget)
                self._schedule_enabled = True
                continue
            self._widget_area_layout.insertWidget(self._widget_area_layout.count() - 1, widget)
        self._apply_left_split()

    def open_config_panel(self) -> None:
        if self._config_window is None:
            self._config_window = ConfigWindow(
                self._widget_store,
                on_widgets_changed=self.render_widgets,
                sync_manager=self._sync_manager,
                current_panel_alpha=self._panel_alpha,
                on_panel_alpha_changed=self.set_panel_alpha,
                current_calendar_font_scale=load_calendar_font_scale(self._calendar_screen_signature),
                current_calendar_screen_label=self._calendar_screen_label,
                on_calendar_font_scale_changed=self._set_current_calendar_font_scale,
                on_holidays_changed=self._calendar.render,
            )
        self._config_window.show()
        self._config_window.raise_()
        self._config_window.activateWindow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_left_container"):
            return  # 构造阶段 _restore_geometry() 里的 resize() 也会触发这个事件，那时子控件还没建好
        self._adjust_overlay.setGeometry(self.rect())
        if hasattr(self, "_guided_tour"):
            self._guided_tour.setGeometry(self.rect())
        self.set_left_area_width(self._left_area_width)
        self._apply_left_split()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        window_handle = self.windowHandle()
        if window_handle is not None and not self._screen_signal_connected:
            window_handle.screenChanged.connect(lambda _screen: self._refresh_calendar_font_for_current_screen())
            self._screen_signal_connected = True
        self._refresh_calendar_font_for_current_screen()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._refresh_calendar_font_for_current_screen()

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

    def set_tour_tray_hint_callback(self, callback: Callable[[], None]) -> None:
        self._tour_tray_hint_callback = callback

    def maybe_start_guided_tour(self) -> None:
        if get_main_tour_completed_version() < TOUR_VERSION:
            self.start_guided_tour()

    def start_guided_tour(self) -> None:
        self._guided_tour.setGeometry(self.rect())
        self._guided_tour.start()

    def _mark_guided_tour_completed(self) -> None:
        mark_main_tour_completed(TOUR_VERSION)

    def _on_guided_tour_step_changed(self, step_key: str) -> None:
        if step_key == "tray" and self._tour_tray_hint_callback is not None:
            self._tour_tray_hint_callback()

    def _guided_tour_anchor(self, key: str) -> Optional[QRect]:
        if key == "calendar_day":
            widget = self._calendar.tour_target_cell()
        elif key == "widgets":
            widget = self._widget_area_scroll
        elif key == "schedule":
            widget = self._schedule_scroll if self._schedule_enabled and self._schedule_scroll.isVisible() else None
        else:
            widget = None
        if widget is None or not widget.isVisible():
            return None

        top_left = widget.mapTo(self, QPoint(0, 0))
        rect = QRect(top_left, widget.size()).intersected(self.rect())
        if key in {"widgets", "schedule"} and rect.height() > 220:
            rect.setHeight(220)
        return rect if rect.isValid() else None
