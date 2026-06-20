"""Gist 同步管理器：定时轮询 + 手动立即同步。

网络调用（pull/merge/push）全部在后台 QThread 里做，结果通过信号送回主线程后才真正
写入 TaskStore——这样所有跨线程共享的可变状态（store 的字典）只在主线程被修改，
避免后台线程和 UI 线程同时改同一份数据。失败时只记日志、发状态信号，不弹错误框。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from deskcal.core.models import DatedTask, FloatingTask
from deskcal.core.storage import TaskStore
from deskcal.core.sync import SyncProvider, merge_payloads

logger = logging.getLogger("deskcal.sync")

DEFAULT_SYNC_INTERVAL_MS = 5 * 60 * 1000  # 5 分钟


class _SyncOnceThread(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, provider: SyncProvider, local_payload: dict, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._local_payload = local_payload

    def run(self) -> None:
        try:
            remote_payload = self._provider.pull()
            merged = merge_payloads(self._local_payload, remote_payload)
            self._provider.push(merged)
            self.succeeded.emit(merged)
        except Exception as exc:  # 静默容错：只记日志和状态信号，绝不弹窗
            logger.exception("同步失败，将在下一轮重试")
            self.failed.emit(str(exc))


class SyncManager(QObject):
    state_changed = pyqtSignal(str)
    data_changed = pyqtSignal()

    def __init__(
        self,
        store: TaskStore,
        provider: SyncProvider,
        interval_ms: int = DEFAULT_SYNC_INTERVAL_MS,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._provider = provider
        self._thread: Optional[_SyncOnceThread] = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.sync_now)
        self._timer.start(interval_ms)

    def sync_now(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return  # 已经在同步，跳过这一次，避免并发

        local_payload = {
            "dated_tasks": [t.to_dict() for t in self._store.dated_tasks.values()],
            "floating_tasks": [t.to_dict() for t in self._store.floating_tasks.values()],
        }
        self._thread = _SyncOnceThread(self._provider, local_payload, self)
        self._thread.succeeded.connect(self._on_succeeded)
        self._thread.failed.connect(self._on_failed)
        self.state_changed.emit("同步中…")
        self._thread.start()

    def _on_succeeded(self, merged: dict) -> None:
        self._store.dated_tasks = {item["id"]: DatedTask.from_dict(item) for item in merged["dated_tasks"]}
        self._store.floating_tasks = {
            item["id"]: FloatingTask.from_dict(item) for item in merged["floating_tasks"]
        }
        self._store.purge_old_tombstones()
        self._store.save()
        self.state_changed.emit(f"上次同步成功：{datetime.now().strftime('%H:%M:%S')}")
        self.data_changed.emit()

    def _on_failed(self, message: str) -> None:
        self.state_changed.emit(f"同步失败（{message}），已记录日志，将自动重试")
