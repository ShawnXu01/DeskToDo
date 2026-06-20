"""Phase 1 自检：验证 deskcal.core.storage 的读写、软删除、墓碑清理逻辑。"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from deskcal.core.models import DatedTask, FloatingTask, Priority, RecurrenceRule, RecurrenceType
from deskcal.core.storage import TaskStore


@pytest.fixture
def tmp_store(tmp_path):
    return TaskStore(file_path=tmp_path / "tasks.json")


def _make_dated_task(name="任务", priority=Priority.RED, day=date(2026, 6, 20)):
    rule = RecurrenceRule(type=RecurrenceType.ONCE, date=day)
    return DatedTask.create(name, priority, rule)


def test_save_and_load_round_trip(tmp_store):
    dated = _make_dated_task()
    floating = FloatingTask.create("浮动任务", Priority.GREEN)
    tmp_store.add_dated_task(dated)
    tmp_store.add_floating_task(floating)
    tmp_store.save()

    assert tmp_store.file_path.exists()

    reloaded = TaskStore(file_path=tmp_store.file_path)
    reloaded.load()
    assert dated.id in reloaded.dated_tasks
    assert floating.id in reloaded.floating_tasks
    assert reloaded.dated_tasks[dated.id].name == "任务"
    assert reloaded.floating_tasks[floating.id].priority is Priority.GREEN


def test_load_missing_file_results_in_empty_store(tmp_store):
    tmp_store.load()
    assert tmp_store.dated_tasks == {}
    assert tmp_store.floating_tasks == {}


def test_atomic_write_leaves_no_temp_files(tmp_store):
    tmp_store.add_floating_task(FloatingTask.create("x", Priority.WHITE))
    tmp_store.save()
    leftovers = list(tmp_store.file_path.parent.glob(".tmp_*"))
    assert leftovers == []


def test_soft_delete_excludes_from_active_iteration(tmp_store):
    dated = _make_dated_task()
    floating = FloatingTask.create("浮动", Priority.ORANGE)
    tmp_store.add_dated_task(dated)
    tmp_store.add_floating_task(floating)

    tmp_store.soft_delete(dated.id)

    assert list(tmp_store.iter_active_dated_tasks()) == []
    assert list(tmp_store.iter_active_floating_tasks()) == [floating]


def test_soft_delete_missing_task_raises(tmp_store):
    with pytest.raises(KeyError):
        tmp_store.soft_delete("不存在的id")


def test_purge_old_tombstones_only_removes_expired(tmp_store):
    old_task = _make_dated_task(name="老墓碑")
    old_task.soft_delete()
    old_task.deleted_at = datetime.now() - timedelta(days=100)

    recent_task = _make_dated_task(name="新墓碑")
    recent_task.soft_delete()  # 刚删除，未过期

    tmp_store.add_dated_task(old_task)
    tmp_store.add_dated_task(recent_task)

    purged = tmp_store.purge_old_tombstones(retention_days=90)

    assert purged == 1
    assert old_task.id not in tmp_store.dated_tasks
    assert recent_task.id in tmp_store.dated_tasks


def test_get_task_finds_in_either_collection(tmp_store):
    dated = _make_dated_task()
    floating = FloatingTask.create("浮动", Priority.GREEN)
    tmp_store.add_dated_task(dated)
    tmp_store.add_floating_task(floating)

    assert tmp_store.get_task(dated.id) is dated
    assert tmp_store.get_task(floating.id) is floating
    assert tmp_store.get_task("不存在") is None
