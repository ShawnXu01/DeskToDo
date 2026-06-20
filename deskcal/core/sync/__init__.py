"""同步层抽象：V1 只有 Gist 一种 SyncProvider 实现，V2 接入飞书时复用这层接口
（详见 docs/v2-mobile-sync-plan.md）。不依赖 PyQt6，合并策略是纯逻辑，可以直接单元测试。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class SyncProvider(ABC):
    @abstractmethod
    def pull(self) -> dict:
        """拉取远端完整的 {"dated_tasks": [...], "floating_tasks": [...]} 数据。"""

    @abstractmethod
    def push(self, payload: dict) -> None:
        """把完整数据推送到远端，覆盖远端内容。"""

    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接是否可用，不抛异常，返回布尔值。"""


def merge_payloads(local: dict, remote: dict) -> dict:
    """按 updated_at 时间戳合并：新的覆盖旧的；任一方独有的任务都保留（包括软删除的墓碑）。"""
    return {
        "dated_tasks": _merge_task_list(local.get("dated_tasks", []), remote.get("dated_tasks", [])),
        "floating_tasks": _merge_task_list(local.get("floating_tasks", []), remote.get("floating_tasks", [])),
    }


def _merge_task_list(local_items: list[dict], remote_items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {item["id"]: item for item in local_items}
    for item in remote_items:
        existing = merged.get(item["id"])
        if existing is None or _is_newer(item, existing):
            merged[item["id"]] = item
    return list(merged.values())


def _is_newer(candidate: dict, existing: dict) -> bool:
    return datetime.fromisoformat(candidate["updated_at"]) > datetime.fromisoformat(existing["updated_at"])
