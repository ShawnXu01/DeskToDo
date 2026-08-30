"""凭证加密与本地存储：基于 Windows DPAPI（绑定当前用户身份，无需自己管理密钥）。

目前唯一需要加密保存的凭证是用户自己的 GitHub Gist Token；
另外用一个独立的 onboarding_completed 标记区分"已经走过引导流程"和"已填 Token"，
这样用户在向导里点"跳过"之后，下次启动不会再弹向导，但仍可以去设置面板里补填。
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import json
from typing import Optional

from deskcal.core.storage import atomic_write_json, get_data_dir

CREDENTIALS_FILE_NAME = "credentials.json"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _to_blob(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    blob = _DataBlob()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))
    return blob


def encrypt(plaintext: str) -> bytes:
    data = plaintext.encode("utf-8")
    in_blob = _to_blob(data)
    out_blob = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return bytes(ctypes.cast(out_blob.pbData, ctypes.POINTER(ctypes.c_ubyte * out_blob.cbData)).contents)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def decrypt(ciphertext: bytes) -> str:
    in_blob = _to_blob(ciphertext)
    out_blob = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        raise ctypes.WinError()
    try:
        data = bytes(ctypes.cast(out_blob.pbData, ctypes.POINTER(ctypes.c_ubyte * out_blob.cbData)).contents)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return data.decode("utf-8")


def get_credentials_file():
    return get_data_dir() / CREDENTIALS_FILE_NAME


def _load_payload() -> dict:
    path = get_credentials_file()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_payload(payload: dict) -> None:
    atomic_write_json(get_credentials_file(), payload)


def is_onboarding_completed() -> bool:
    return bool(_load_payload().get("onboarding_completed", False))


def mark_onboarding_completed() -> None:
    payload = _load_payload()
    payload["onboarding_completed"] = True
    _save_payload(payload)


def save_gist_token(token: str) -> None:
    payload = _load_payload()
    payload["github_gist_token"] = base64.b64encode(encrypt(token)).decode("ascii")
    _save_payload(payload)


def load_gist_token() -> Optional[str]:
    encoded = _load_payload().get("github_gist_token")
    if not encoded:
        return None
    return decrypt(base64.b64decode(encoded))


def save_gist_id(gist_id: str) -> None:
    payload = _load_payload()
    payload["github_gist_id"] = gist_id
    _save_payload(payload)


def clear_gist_id() -> None:
    payload = _load_payload()
    payload.pop("github_gist_id", None)
    _save_payload(payload)


def load_gist_id() -> Optional[str]:
    return _load_payload().get("github_gist_id")
