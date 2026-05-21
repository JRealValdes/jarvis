"""Smoke tests for canonical core and infrastructure imports."""

from core.config import DEFAULT_MODEL, USE_MCP
from core.enums import ModelEnum
from infrastructure.crypto.fernet import decode_symm_crypt_key, encode_symm_crypt_key


def test_core_config_defaults():
    assert DEFAULT_MODEL == ModelEnum.GPT_3_5
    assert USE_MCP is False


def test_fernet_helpers_are_callable():
    assert callable(encode_symm_crypt_key)
    assert callable(decode_symm_crypt_key)


def test_interfaces_gradio_demo_importable():
    from interfaces.gradio_app import demo, respond, reset_chat

    assert demo is not None
    assert callable(respond)
    assert callable(reset_chat)
