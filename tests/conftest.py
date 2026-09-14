"""Every test gets disposable storage; never touch the tracked personal journal."""
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database
import api


@pytest.fixture(autouse=True)
def isolate_storage_and_network(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("TEACHHELPER_NO_BOT", "1")
    path = str(tmp_path / "journal.db")
    monkeypatch.setattr(database, "DB_PATH", path)
    monkeypatch.setattr(api, "_DB_PATH", path)
    with database.Database(path):
        pass
    def no_network(*args, **kwargs):
        raise AssertionError("Real network calls are forbidden in tests")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    yield
    for registry in (api._pending, api._pending_curator):
        for timer in list(registry.values()):
            timer.cancel()
        registry.clear()
