"""Phase 6 自检：验证 merge_payloads 的时间戳覆盖合并逻辑，不依赖网络/PyQt6。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deskcal.core.sync import merge_payloads


def _task(task_id, updated_at, name="t"):
    return {
        "id": task_id,
        "name": name,
        "updated_at": updated_at,
        "priority": 1,
        "recurrence": {"type": "once", "date": "2026-06-20", "start": None, "end": None, "weekdays": None, "dates": None},
        "created_at": "2026-06-01T00:00:00",
        "completed_dates": [],
        "deleted_at": None,
        "source": "local",
    }


def test_local_only_task_is_kept():
    local = {"dated_tasks": [_task("a", "2026-06-18T10:00:00")], "floating_tasks": []}
    remote = {"dated_tasks": [], "floating_tasks": []}
    merged = merge_payloads(local, remote)
    assert [t["id"] for t in merged["dated_tasks"]] == ["a"]


def test_remote_only_task_is_added():
    local = {"dated_tasks": [], "floating_tasks": []}
    remote = {"dated_tasks": [_task("b", "2026-06-18T10:00:00")], "floating_tasks": []}
    merged = merge_payloads(local, remote)
    assert [t["id"] for t in merged["dated_tasks"]] == ["b"]


def test_newer_remote_overwrites_older_local():
    local = {"dated_tasks": [_task("a", "2026-06-18T08:00:00", name="旧版本")], "floating_tasks": []}
    remote = {"dated_tasks": [_task("a", "2026-06-18T12:00:00", name="新版本")], "floating_tasks": []}
    merged = merge_payloads(local, remote)
    assert merged["dated_tasks"][0]["name"] == "新版本"


def test_older_remote_does_not_overwrite_newer_local():
    local = {"dated_tasks": [_task("a", "2026-06-18T12:00:00", name="本地新")], "floating_tasks": []}
    remote = {"dated_tasks": [_task("a", "2026-06-18T08:00:00", name="远端旧")], "floating_tasks": []}
    merged = merge_payloads(local, remote)
    assert merged["dated_tasks"][0]["name"] == "本地新"


def test_deletion_with_newer_timestamp_wins_over_edit():
    edited = _task("a", "2026-06-18T08:00:00", name="被编辑")
    deleted = _task("a", "2026-06-18T12:00:00", name="被编辑")
    deleted["deleted_at"] = "2026-06-18T12:00:00"

    local = {"dated_tasks": [deleted], "floating_tasks": []}
    remote = {"dated_tasks": [edited], "floating_tasks": []}
    merged = merge_payloads(local, remote)
    assert merged["dated_tasks"][0]["deleted_at"] is not None


def test_floating_tasks_merged_independently_of_dated_tasks():
    local = {"dated_tasks": [], "floating_tasks": [_task("f1", "2026-06-18T10:00:00")]}
    remote = {"dated_tasks": [_task("d1", "2026-06-18T10:00:00")], "floating_tasks": []}
    merged = merge_payloads(local, remote)
    assert [t["id"] for t in merged["floating_tasks"]] == ["f1"]
    assert [t["id"] for t in merged["dated_tasks"]] == ["d1"]
