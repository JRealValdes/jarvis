"""Environment-driven config (no network)."""

import importlib

import pytest

from jarvis.core.enums import IdentificationFailedProtocolEnum, ModelEnum


@pytest.fixture(autouse=True)
def _restore_config_module(monkeypatch: pytest.MonkeyPatch):
    """
    Keep ``jarvis.core.config`` at process defaults after each test.

    Reloading the module for assertions would otherwise leak into later tests.
    """
    for name in (
        "JARVIS_USE_MCP",
        "JARVIS_DEFAULT_MODEL",
        "JARVIS_IDENTIFICATION_FAILED_PROTOCOL",
        "JARVIS_DB_DEBUG_MODE",
        "JARVIS_EXPOSE_API_WITH_CLOUDFLARED",
        "JWT_ALGORITHM",
        "JWT_EXP_DELTA_SECONDS",
        "API_PORT",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    for name in (
        "JARVIS_USE_MCP",
        "JARVIS_DEFAULT_MODEL",
        "JARVIS_IDENTIFICATION_FAILED_PROTOCOL",
        "JARVIS_DB_DEBUG_MODE",
        "JARVIS_EXPOSE_API_WITH_CLOUDFLARED",
        "JWT_ALGORITHM",
        "JWT_EXP_DELTA_SECONDS",
        "API_PORT",
    ):
        monkeypatch.delenv(name, raising=False)
    import jarvis.core.config as config

    importlib.reload(config)


def _reload_config():
    import jarvis.core.config as config

    return importlib.reload(config)


def test_config_defaults_when_unset(monkeypatch: pytest.MonkeyPatch):
    config = _reload_config()
    assert config.DEFAULT_MODEL == ModelEnum.GPT_4O_MINI
    assert (
        config.IDENTIFICATION_FAILED_PROTOCOL
        == IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE
    )
    assert config.DB_DEBUG_MODE is False
    assert config.EXPOSE_API_WITH_CLOUDFLARED is False
    assert config.JWT_ALGORITHM == "HS256"
    assert config.JWT_EXP_DELTA_SECONDS == 3600
    assert config.USE_MCP is False
    assert config.API_PORT == 8000


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_use_mcp_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setenv("JARVIS_USE_MCP", value)
    assert _reload_config().USE_MCP is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "maybe"])
def test_use_mcp_falsy_values(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setenv("JARVIS_USE_MCP", value)
    assert _reload_config().USE_MCP is False


def test_default_model_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_DEFAULT_MODEL", "GPT_3_5")
    assert _reload_config().DEFAULT_MODEL == ModelEnum.GPT_3_5


def test_default_model_rejects_unknown(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_DEFAULT_MODEL", "not_a_model")
    with pytest.raises(ValueError, match="JARVIS_DEFAULT_MODEL"):
        _reload_config()


def test_api_port_and_jwt_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_PORT", "9001")
    monkeypatch.setenv("JWT_ALGORITHM", "HS512")
    monkeypatch.setenv("JWT_EXP_DELTA_SECONDS", "120")
    config = _reload_config()
    assert config.API_PORT == 9001
    assert config.JWT_ALGORITHM == "HS512"
    assert config.JWT_EXP_DELTA_SECONDS == 120


def test_identification_protocol_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "JARVIS_IDENTIFICATION_FAILED_PROTOCOL", "HOSTILE_RESPONSES"
    )
    assert (
        _reload_config().IDENTIFICATION_FAILED_PROTOCOL
        == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES
    )
