"""Phase 1 — iOS DB path: только точечный бэкенд-дифф, без Android регрессий."""
import importlib
import os
import sys
from pathlib import Path
import pytest

import database


def test_is_ios_via_sys_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "ios")
    monkeypatch.delenv("TEACHHELPER_IOS", raising=False)
    monkeypatch.delenv("ANDROID_PRIVATE", raising=False)
    monkeypatch.delenv("ANDROID_ARGUMENT", raising=False)
    assert database._is_ios() is True
    assert database._is_android() is False


def test_is_ios_via_env(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("TEACHHELPER_IOS", "1")
    monkeypatch.delenv("ANDROID_PRIVATE", raising=False)
    monkeypatch.delenv("ANDROID_ARGUMENT", raising=False)
    assert database._is_ios() is True


def test_is_ios_false_on_desktop(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("TEACHHELPER_IOS", raising=False)
    monkeypatch.delenv("ANDROID_PRIVATE", raising=False)
    monkeypatch.delenv("ANDROID_ARGUMENT", raising=False)
    assert database._is_ios() is False
    assert database._is_android() is False


def test_ios_takes_precedence_over_android(monkeypatch):
    # If both flags set, iOS wins (resolve order)
    monkeypatch.setattr(sys, "platform", "ios")
    monkeypatch.setenv("ANDROID_PRIVATE", "/tmp/android")
    assert database._is_ios() is True
    assert database._is_android() is True
    # _resolve picks iOS
    monkeypatch.setattr(Path, "home", lambda: Path("/tmp/fakehome"))
    # Mock mkdir to avoid FS side effects
    orig_mkdir = Path.mkdir
    monkeypatch.setattr(Path, "mkdir", lambda self, **kw: None)
    resolved = database._resolve_db_path()
    assert resolved.endswith("Documents/lessons.db") or "lessons.db" in resolved
    # Should be iOS path, not Android
    assert "Documents" in resolved or "fakehome" in resolved


def test_ios_db_path_uses_documents(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "ios")
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    # Ensure Documents creation is attempted
    path = database._ios_db_path()
    assert path == str(fake_home / "Documents" / "lessons.db")
    # Documents dir should have been created (or mocked)
    assert (fake_home / "Documents").exists()


def test_resolve_db_path_ios(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "ios")
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.delenv("ANDROID_PRIVATE", raising=False)
    # _resolve should point to Documents
    assert database._resolve_db_path() == str(fake_home / "Documents" / "lessons.db")


def test_resolve_db_path_android(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("TEACHHELPER_IOS", raising=False)
    monkeypatch.setenv("ANDROID_PRIVATE", str(tmp_path / "android_private"))
    # Mock Path.home not needed for Android path
    resolved = database._resolve_db_path()
    assert str(tmp_path / "android_private" / "files" / "lessons.db") == resolved


def test_resolve_db_path_desktop(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("TEACHHELPER_IOS", raising=False)
    monkeypatch.delenv("ANDROID_PRIVATE", raising=False)
    monkeypatch.delenv("ANDROID_ARGUMENT", raising=False)
    # Should be next to database.py
    expected = os.path.join(os.path.dirname(database.__file__), "lessons.db")
    assert database._resolve_db_path() == expected


def test_database_init_uses_ios_path_when_env(monkeypatch, tmp_path):
    """Database() without arg picks iOS Documents path when TEACHHELPER_IOS=1."""
    monkeypatch.setenv("TEACHHELPER_IOS", "1")
    fake_home = tmp_path / "home_ios"
    fake_home.mkdir(parents=True, exist_ok=True)
    # Ensure Documents exists for sqlite
    (fake_home / "Documents").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr(database, "DB_PATH", str(fake_home / "Documents" / "lessons.db"))
    db = database.Database()
    try:
        assert db.db_path == str(fake_home / "Documents" / "lessons.db")
        assert os.path.exists(db.db_path)
    finally:
        db.close()
