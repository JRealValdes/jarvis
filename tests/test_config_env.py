"""Environment-driven config flags (no network)."""

import importlib

import pytest


@pytest.fixture(autouse=True)
def _restore_config_module(monkeypatch: pytest.MonkeyPatch):
    """
    Keep ``jarvis.core.config.USE_MCP`` at the process default after each test.

    Reloading the module for assertions would otherwise leak into later tests.
    """
    monkeypatch.delenv("JARVIS_USE_MCP", raising=False)
    yield
    monkeypatch.delenv("JARVIS_USE_MCP", raising=False)
    import jarvis.core.config as config

    importlib.reload(config)


def test_use_mcp_defaults_false_when_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("JARVIS_USE_MCP", raising=False)
    import jarvis.core.config as config

    importlib.reload(config)
    assert config.USE_MCP is False
    assert config._env_flag("JARVIS_USE_MCP", default=False) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_use_mcp_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setenv("JARVIS_USE_MCP", value)
    import jarvis.core.config as config

    importlib.reload(config)
    assert config.USE_MCP is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "maybe"])
def test_use_mcp_falsy_values(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setenv("JARVIS_USE_MCP", value)
    import jarvis.core.config as config

    importlib.reload(config)
    assert config.USE_MCP is False
