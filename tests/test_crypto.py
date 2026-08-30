"""Phase 5 自检：验证 DPAPI 加解密往返，以及凭证文件的 onboarding/token 持久化逻辑。

用 monkeypatch 把 get_credentials_file 指向临时目录，避免污染真实的 %APPDATA%/DeskCal/credentials.json。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deskcal.utils import crypto


def test_encrypt_decrypt_round_trip():
    plaintext = "ghp_some_fake_token_abcdef123456"
    ciphertext = crypto.encrypt(plaintext)
    assert isinstance(ciphertext, bytes)
    assert ciphertext != plaintext.encode("utf-8")
    assert crypto.decrypt(ciphertext) == plaintext


def test_onboarding_and_token_persistence(tmp_path, monkeypatch):
    fake_file = tmp_path / "credentials.json"
    monkeypatch.setattr(crypto, "get_credentials_file", lambda: fake_file)

    assert crypto.is_onboarding_completed() is False
    assert crypto.load_gist_token() is None

    crypto.save_gist_token("ghp_real_looking_token")
    crypto.mark_onboarding_completed()

    assert crypto.is_onboarding_completed() is True
    assert crypto.load_gist_token() == "ghp_real_looking_token"

    # 确认本地文件里没有明文 token
    raw_text = fake_file.read_text(encoding="utf-8")
    assert "ghp_real_looking_token" not in raw_text


def test_skip_only_marks_completed_without_token(tmp_path, monkeypatch):
    fake_file = tmp_path / "credentials.json"
    monkeypatch.setattr(crypto, "get_credentials_file", lambda: fake_file)

    crypto.mark_onboarding_completed()

    assert crypto.is_onboarding_completed() is True
    assert crypto.load_gist_token() is None


def test_clear_gist_id_preserves_other_credentials(tmp_path, monkeypatch):
    fake_file = tmp_path / "credentials.json"
    monkeypatch.setattr(crypto, "get_credentials_file", lambda: fake_file)

    crypto.save_gist_token("ghp_real_looking_token")
    crypto.mark_onboarding_completed()
    crypto.save_gist_id("invalid-gist-id")

    crypto.clear_gist_id()

    assert crypto.load_gist_id() is None
    assert crypto.load_gist_token() == "ghp_real_looking_token"
    assert crypto.is_onboarding_completed() is True
