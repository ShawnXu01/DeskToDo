"""Phase 4 自检：验证 WidgetConfigStore 的持久化、启用、排序、配置更新逻辑。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _pyqt6_stub import ensure_pyqt6_importable

ensure_pyqt6_importable()

import pytest

from deskcal.ui.desktop_overlay.widgets.registry import DEFAULT_ORDER, WidgetConfigStore


@pytest.fixture
def tmp_store(tmp_path):
    return WidgetConfigStore(file_path=tmp_path / "widgets.json")


def test_load_missing_file_creates_defaults_in_default_order(tmp_store):
    tmp_store.load()
    assert [item.type_id for item in tmp_store.items] == DEFAULT_ORDER
    assert all(item.enabled for item in tmp_store.items)


def test_save_and_reload_round_trip(tmp_store):
    tmp_store.load()
    tmp_store.set_enabled(0, False)
    tmp_store.update_config(1, {"items": [{"title": "AAAI", "deadline": "2026-07-21T23:59:00"}]})
    tmp_store.save()

    reloaded = WidgetConfigStore(file_path=tmp_store.file_path)
    reloaded.load()
    assert reloaded.items[0].enabled is False
    assert reloaded.items[1].config["items"][0]["title"] == "AAAI"


def test_enabled_items_filters_disabled(tmp_store):
    tmp_store.load()
    tmp_store.set_enabled(0, False)
    enabled_ids = [item.type_id for item in tmp_store.enabled_items()]
    assert DEFAULT_ORDER[0] not in enabled_ids
    assert len(enabled_ids) == len(DEFAULT_ORDER) - 1


def test_move_up_swaps_with_previous(tmp_store):
    tmp_store.load()
    original = [item.type_id for item in tmp_store.items]
    tmp_store.move_up(1)
    assert tmp_store.items[0].type_id == original[1]
    assert tmp_store.items[1].type_id == original[0]


def test_move_up_at_top_is_noop(tmp_store):
    tmp_store.load()
    original = [item.type_id for item in tmp_store.items]
    tmp_store.move_up(0)
    assert [item.type_id for item in tmp_store.items] == original


def test_move_down_at_bottom_is_noop(tmp_store):
    tmp_store.load()
    original = [item.type_id for item in tmp_store.items]
    tmp_store.move_down(len(original) - 1)
    assert [item.type_id for item in tmp_store.items] == original
