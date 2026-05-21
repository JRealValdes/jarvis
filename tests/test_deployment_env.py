"""Tests for environment variable reads in api.deployment."""

import jarvis.api.deployment as deployment


def test_telegram_config_reads_from_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    bot, chat = deployment._telegram_config()

    assert bot == "test-bot-token"
    assert chat == "12345"


def test_firebase_config_reads_from_environment(monkeypatch):
    monkeypatch.setenv("FIREBASE_DB_URL", "https://example.firebaseio.com")
    monkeypatch.setenv("FIREBASE_NODE_PATH", "jarvis/test_url")

    fb_url, fb_path = deployment._firebase_config()

    assert fb_url == "https://example.firebaseio.com"
    assert fb_path == "jarvis/test_url"


def test_firebase_config_default_node_path(monkeypatch):
    monkeypatch.delenv("FIREBASE_NODE_PATH", raising=False)
    monkeypatch.setenv("FIREBASE_DB_URL", "https://example.firebaseio.com")

    _, fb_path = deployment._firebase_config()

    assert fb_path == "jarvis/latest_url"
