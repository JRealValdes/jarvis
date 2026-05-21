"""Tests de shims de compatibilidad (config, enums, security)."""

import config as root_config
import enums.core_enums as root_enums
from core.config import DEFAULT_MODEL as core_default
from core.enums.core_enums import ModelEnum as CoreModelEnum
from utils import security as root_security


def test_config_shim_matches_core():
    assert root_config.DEFAULT_MODEL is core_default
    assert root_config.USE_MCP is False


def test_enums_shim_matches_core():
    assert root_enums.ModelEnum.GPT_3_5 is CoreModelEnum.GPT_3_5


def test_security_shim_exports_fernet_helpers():
    assert hasattr(root_security, "encode_symm_crypt_key")
    assert hasattr(root_security, "decode_symm_crypt_key")


def test_interfaces_gradio_demo_importable():
    from interfaces.gradio_app import demo, respond, reset_chat

    assert demo is not None
    assert callable(respond)
    assert callable(reset_chat)
