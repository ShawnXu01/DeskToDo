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
GIST_DESCRIPTION = "DeskToDo 任务数据（自动同步，请勿手动编辑）"
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

        discovered_id = self._discover_existing_gist()
        if discovered_id:
            crypto.save_gist_id(discovered_id)
            self._gist_id = discovered_id
            return discovered_id

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

    def _discover_existing_gist(self) -> Optional[str]:
        """本地没记到 gist_id 时，先看这个账号下是否已经有一个带着我们固定描述的 Gist 可以直接接上，
        避免每台新电脑/重新引导都各自新建一个空 Gist 导致数据互不相通。"""
        for page in range(1, 4):  # 最多翻 3 页（每页 100 条），覆盖绝大多数账号
            response = requests.get(
                f"{API_BASE}/gists",
                headers=self._headers(),
                params={"per_page": 100, "page": page},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            items = response.json()
            for item in items:
                if item.get("description") == GIST_DESCRIPTION and GIST_FILENAME in item.get("files", {}):
                    return item["id"]
            if len(items) < 100:
                break
        return None

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
