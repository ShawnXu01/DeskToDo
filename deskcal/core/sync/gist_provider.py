"""GitHub Gist 同步实现：用用户自己的一个私密 Gist 存放任务数据 JSON。

gist_id 第一次使用时自动创建并持久化，之后复用；不持有 token 之外的任何凭证。
"""
from __future__ import annotations

import json
from typing import Optional

import requests

from deskcal.core.sync import SyncProvider
from deskcal.utils import crypto

GIST_FILENAME = "deskcal_tasks.json"
GIST_DESCRIPTION = "DeskCal 任务数据（自动同步，请勿手动编辑）"
API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 15

EMPTY_PAYLOAD = {"dated_tasks": [], "floating_tasks": []}


class GistSyncProvider(SyncProvider):
    def __init__(self, token: str):
        self._token = token
        self._gist_id: Optional[str] = None

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github+json",
        }

    def ensure_gist(self) -> str:
        if self._gist_id:
            return self._gist_id

        stored_id = crypto.load_gist_id()
        if stored_id:
            self._gist_id = stored_id
            return self._gist_id

        response = requests.post(
            f"{API_BASE}/gists",
            headers=self._headers(),
            json={
                "description": GIST_DESCRIPTION,
                "public": False,
                "files": {GIST_FILENAME: {"content": json.dumps(EMPTY_PAYLOAD)}},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        gist_id = response.json()["id"]
        crypto.save_gist_id(gist_id)
        self._gist_id = gist_id
        return gist_id

    def pull(self) -> dict:
        gist_id = self.ensure_gist()
        response = requests.get(
            f"{API_BASE}/gists/{gist_id}", headers=self._headers(), timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        data = response.json()
        content = data["files"][GIST_FILENAME]["content"]
        return json.loads(content)

    def push(self, payload: dict) -> None:
        gist_id = self.ensure_gist()
        response = requests.patch(
            f"{API_BASE}/gists/{gist_id}",
            headers=self._headers(),
            json={"files": {GIST_FILENAME: {"content": json.dumps(payload, ensure_ascii=False)}}},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    def test_connection(self) -> bool:
        try:
            response = requests.get(f"{API_BASE}/user", headers=self._headers(), timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False
