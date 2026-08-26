"""本地 JSON 持久化：原子写入、墓碑清理。"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .models import DatedTask, FloatingTask

APP_DIR_NAME = "DeskCal"
TASKS_FILE_NAME = "tasks.json"
WINDOW_STATE_FILE_NAME = "window_state.json"
APPEARANCE_FILE_NAME = "appearance.json"

TOMBSTONE_RETENTION_DAYS = 90
DEFAULT_PANEL_ALPHA = 230
DEFAULT_CONFIG_PANEL_ALPHA = 210


def get_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    data_dir = base / APP_DIR_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_tasks_file() -> Path:
    return get_data_dir() / TASKS_FILE_NAME


def get_window_state_file() -> Path:
    return get_data_dir() / WINDOW_STATE_FILE_NAME


def get_appearance_file() -> Path:
    return get_data_dir() / APPEARANCE_FILE_NAME


def load_appearance() -> dict:
    path = get_appearance_file()
    data = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("panel_alpha", DEFAULT_PANEL_ALPHA)
    data.setdefault("config_panel_alpha", DEFAULT_CONFIG_PANEL_ALPHA)
    data.setdefault("config_background_path", None)
    data.setdefault("autostart_enabled", True)
    return data


def save_appearance(**fields) -> None:
    """按字段合并保存，不会覆盖其它已存的外观设置。"""
    payload = load_appearance()
    payload.update(fields)
    atomic_write_json(get_appearance_file(), payload)


def get_main_tour_completed_version() -> int:
    value = load_appearance().get("main_tour_completed_version", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def mark_main_tour_completed(version: int) -> None:
    if version < 1:
        raise ValueError("引导版本必须大于等于 1")
    save_appearance(main_tour_completed_version=version)


def _load_window_state_payload() -> dict:
    """读取 window_state.json；旧版本（单一一组 x/y/width/height）会迁移成按显示器签名分组的格式。"""
    path = get_window_state_file()
    if not path.exists():
        return {"profiles": {}}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if "profiles" in raw:
        return raw
    if "x" in raw:
        from deskcal.utils.monitor import compute_monitor_signature

        return {"profiles": {compute_monitor_signature(): raw}}
    return {"profiles": {}}


def list_window_profiles() -> dict[str, dict]:
    """返回 {显示器签名: 几何信息}，给设置面板的"显示屏设置"页展示用。"""
    return _load_window_state_payload()["profiles"]


def load_window_geometry(signature: str) -> Optional[dict]:
    return list_window_profiles().get(signature)


def save_window_geometry(
    signature: str,
    x: int,
    y: int,
    width: int,
    height: int,
    left_area_width: int,
    left_top_ratio: float,
    left_split_manual: bool,
) -> None:
    payload = _load_window_state_payload()
    payload["profiles"][signature] = {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "left_area_width": left_area_width,
        "left_top_ratio": left_top_ratio,
        "left_split_manual": left_split_manual,
    }
    atomic_write_json(get_window_state_file(), payload)


def atomic_write_json(path: Path, payload: dict) -> None:
    """先写临时文件再原子替换，避免异常退出时写出半截文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


class TaskStore:
    """持有全部任务，负责加载/保存/软删除/墓碑清理。"""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or get_tasks_file()
        self.dated_tasks: dict[str, DatedTask] = {}
        self.floating_tasks: dict[str, FloatingTask] = {}

    def load(self) -> None:
        self.dated_tasks = {}
        self.floating_tasks = {}
        if not self.file_path.exists():
            return
        with open(self.file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for item in raw.get("dated_tasks", []):
            task = DatedTask.from_dict(item)
            self.dated_tasks[task.id] = task
        for item in raw.get("floating_tasks", []):
            task = FloatingTask.from_dict(item)
            self.floating_tasks[task.id] = task

    def save(self) -> None:
        payload = {
            "dated_tasks": [t.to_dict() for t in self.dated_tasks.values()],
            "floating_tasks": [t.to_dict() for t in self.floating_tasks.values()],
        }
        atomic_write_json(self.file_path, payload)

    def add_dated_task(self, task: DatedTask) -> None:
        self.dated_tasks[task.id] = task

    def add_floating_task(self, task: FloatingTask) -> None:
        self.floating_tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[DatedTask | FloatingTask]:
        return self.dated_tasks.get(task_id) or self.floating_tasks.get(task_id)

    def soft_delete(self, task_id: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        task.soft_delete()

    def iter_active_dated_tasks(self):
        return (t for t in self.dated_tasks.values() if not t.is_deleted)

    def iter_active_floating_tasks(self):
        return (t for t in self.floating_tasks.values() if not t.is_deleted)

    def purge_old_tombstones(self, retention_days: int = TOMBSTONE_RETENTION_DAYS) -> int:
        """物理移除超过保留期的墓碑记录，返回清理条数。"""
        cutoff = datetime.now() - timedelta(days=retention_days)
        purged = 0

        for task_id in [tid for tid, t in self.dated_tasks.items() if t.is_deleted and t.deleted_at < cutoff]:
            del self.dated_tasks[task_id]
            purged += 1

        for task_id in [tid for tid, t in self.floating_tasks.items() if t.is_deleted and t.deleted_at < cutoff]:
            del self.floating_tasks[task_id]
            purged += 1

        return purged
