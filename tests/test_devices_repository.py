"""Unit tests for device token registration."""

from pathlib import Path

import jarvis.infrastructure.persistence.devices.repository as devices_repo
import pytest


def test_register_and_list_tokens(tmp_path: Path, monkeypatch):
    db = tmp_path / "devices.db"
    monkeypatch.setattr(devices_repo, "DB_PATH", str(db))
    monkeypatch.setattr(devices_repo, "DEVICES_DB_PATH", db)

    record = devices_repo.register_device_token(
        owner_real_name="Alice",
        token="token-1",
        platform="android",
    )
    assert record.token == "token-1"
    listed = devices_repo.list_tokens_for_user("Alice")
    assert len(listed) == 1

    devices_repo.register_device_token(
        owner_real_name="Alice",
        token="token-1",
        platform="ios",
    )
    listed = devices_repo.list_tokens_for_user("Alice")
    assert len(listed) == 1
    assert listed[0].platform == "ios"

    assert devices_repo.unregister_device_token(
        owner_real_name="Alice", token="token-1"
    )
    assert devices_repo.list_tokens_for_user("Alice") == []


def test_register_rejects_bad_platform(tmp_path: Path, monkeypatch):
    db = tmp_path / "devices.db"
    monkeypatch.setattr(devices_repo, "DB_PATH", str(db))
    monkeypatch.setattr(devices_repo, "DEVICES_DB_PATH", db)
    with pytest.raises(ValueError, match="platform"):
        devices_repo.register_device_token(
            owner_real_name="Alice", token="t", platform="blackberry"
        )
