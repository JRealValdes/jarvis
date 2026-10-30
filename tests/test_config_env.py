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
        "JARVIS_SHOW_TOOL_TRACES",
        "JARVIS_RANKED_IMAGE_RETRIEVAL",
        "JARVIS_VISION_VERIFY_IMAGES",
        "JARVIS_IMAGE_STORAGE",
        "JARVIS_WEB_IMAGE_TTL_DAYS",
        "JARVIS_GENERATED_IMAGE_TTL_DAYS",
        "JARVIS_PUBLIC_BASE_URL",
        "JARVIS_DEFAULT_MODEL",
        "JARVIS_LOCAL_THREAD_ID",
        "JARVIS_IDENTIFICATION_FAILED_PROTOCOL",
        "JARVIS_DB_DEBUG_MODE",
        "JWT_ALGORITHM",
        "JWT_EXP_DELTA_SECONDS",
        "API_PORT",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    for name in (
        "JARVIS_USE_MCP",
        "JARVIS_SHOW_TOOL_TRACES",
        "JARVIS_RANKED_IMAGE_RETRIEVAL",
        "JARVIS_VISION_VERIFY_IMAGES",
        "JARVIS_IMAGE_STORAGE",
        "JARVIS_WEB_IMAGE_TTL_DAYS",
        "JARVIS_GENERATED_IMAGE_TTL_DAYS",
        "JARVIS_PUBLIC_BASE_URL",
        "JARVIS_DEFAULT_MODEL",
        "JARVIS_LOCAL_THREAD_ID",
        "JARVIS_IDENTIFICATION_FAILED_PROTOCOL",
        "JARVIS_DB_DEBUG_MODE",
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
    assert config.LOCAL_THREAD_ID == "1"
    assert (
        config.IDENTIFICATION_FAILED_PROTOCOL
        == IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE
    )
    assert config.DB_DEBUG_MODE is False
    assert config.JWT_ALGORITHM == "HS256"
    assert config.JWT_EXP_DELTA_SECONDS == 3600
    assert config.USE_MCP is False
    assert config.SHOW_TOOL_TRACES is False
    assert config.RANKED_IMAGE_RETRIEVAL is False
    assert config.VISION_VERIFY_IMAGES is False
    assert config.IMAGE_STORAGE is True
    assert config.WEB_IMAGE_TTL_DAYS == 30
    assert config.GENERATED_IMAGE_TTL_DAYS == 365
    assert config.PUBLIC_BASE_URL == ""
    assert config.API_PORT == 8000


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_use_mcp_truthy_values(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setenv("JARVIS_USE_MCP", value)
    assert _reload_config().USE_MCP is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "maybe"])
def test_use_mcp_falsy_values(monkeypatch: pytest.MonkeyPatch, value: str):
    monkeypatch.setenv("JARVIS_USE_MCP", value)
    assert _reload_config().USE_MCP is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_show_tool_traces_truthy_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("JARVIS_SHOW_TOOL_TRACES", value)
    assert _reload_config().SHOW_TOOL_TRACES is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off"])
def test_show_tool_traces_falsy_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("JARVIS_SHOW_TOOL_TRACES", value)
    assert _reload_config().SHOW_TOOL_TRACES is False


def test_ranked_image_retrieval_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_RANKED_IMAGE_RETRIEVAL", "1")
    assert _reload_config().RANKED_IMAGE_RETRIEVAL is True


def test_vision_verify_images_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_VISION_VERIFY_IMAGES", "on")
    assert _reload_config().VISION_VERIFY_IMAGES is True


def test_image_storage_settings_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_IMAGE_STORAGE", "0")
    monkeypatch.setenv("JARVIS_WEB_IMAGE_TTL_DAYS", "0")
    monkeypatch.setenv("JARVIS_GENERATED_IMAGE_TTL_DAYS", "10")
    monkeypatch.setenv("JARVIS_PUBLIC_BASE_URL", "http://jarvis.example:8000/")
    config = _reload_config()
    assert config.IMAGE_STORAGE is False
    assert config.WEB_IMAGE_TTL_DAYS == 0
    assert config.GENERATED_IMAGE_TTL_DAYS == 10
    assert config.PUBLIC_BASE_URL == "http://jarvis.example:8000/"


def test_image_ttl_rejects_negative(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_WEB_IMAGE_TTL_DAYS", "-1")
    with pytest.raises(ValueError, match="JARVIS_WEB_IMAGE_TTL_DAYS"):
        _reload_config()


def test_local_thread_id_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JARVIS_LOCAL_THREAD_ID", "operator")
    assert _reload_config().LOCAL_THREAD_ID == "operator"


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


def test_required_secrets_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-test")
    monkeypatch.setenv("FERNET_KEY", "fernet-test")
    config = _reload_config()
    assert config.get_jwt_secret_key() == "jwt-test"
    assert config.get_fernet_key() == "fernet-test"


def test_required_secret_raises_when_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "  ")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is not set"):
        _reload_config().get_jwt_secret_key()
