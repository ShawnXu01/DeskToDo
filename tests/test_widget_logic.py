"""Phase 4 自检：验证不依赖 PyQt6 的纯逻辑函数（倒计时格式化、进度百分比）。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _pyqt6_stub import ensure_pyqt6_importable

ensure_pyqt6_importable()

from deskcal.ui.desktop_overlay.widgets.countdown_widget import format_remaining
from deskcal.ui.desktop_overlay.widgets.progress_widget import compute_percent


def test_format_remaining_future():
    assert format_remaining(60 * 60 * 24 * 2 + 60 * 60 * 3 + 60 * 5) == "2天3时5分"


def test_format_remaining_hours_only():
    assert format_remaining(60 * 60 * 5 + 60 * 10) == "5时10分"


def test_format_remaining_minutes_only():
    assert format_remaining(60 * 30) == "30分"


def test_format_remaining_overdue_shows_negative():
    assert format_remaining(-60 * 90) == "-1时30分"


def test_compute_percent_before_start():
    assert compute_percent(date(2026, 6, 1), date(2026, 7, 1), date(2026, 5, 1)) == 0


def test_compute_percent_after_end_caps_at_100():
    assert compute_percent(date(2026, 6, 1), date(2026, 7, 1), date(2026, 12, 1)) == 100


def test_compute_percent_midpoint():
    # 6/1 ~ 7/1 共 30 天，6/16 是第15天 -> 50%
    assert compute_percent(date(2026, 6, 1), date(2026, 7, 1), date(2026, 6, 16)) == 50


def test_compute_percent_zero_length_range():
    assert compute_percent(date(2026, 6, 1), date(2026, 6, 1), date(2026, 6, 1)) == 100
