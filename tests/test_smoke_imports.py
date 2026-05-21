"""Smoke tests: core modules import and public session API is callable."""

import inspect

from agents.factory import build_agent, models_with_memory
from agents.session import (
    ask_jarvis,
    check_individual_session_cache_exists,
    get_cache_status,
    reset_cache_global,
)
from core.config import DEFAULT_MODEL
from core.enums import IdentificationFailedProtocolEnum, ModelEnum


def test_model_enum_members():
    assert ModelEnum.GPT_3_5.value == "chatgpt_3_5"
    assert len(ModelEnum) >= 4


def test_identification_failed_protocol_enum():
    assert IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE.value == "automatic_response"


def test_default_model_is_gpt_35():
    assert DEFAULT_MODEL == ModelEnum.GPT_3_5


def test_models_with_memory_includes_default():
    assert DEFAULT_MODEL in models_with_memory


def test_build_agent_factory_returns_object():
    agent = build_agent(ModelEnum.ZEPHYR)
    assert agent is not None
    assert hasattr(agent, "invoke")


def test_ask_jarvis_is_callable():
    assert callable(ask_jarvis)
    sig = inspect.signature(ask_jarvis)
    assert "prompt" in sig.parameters
    assert "thread_id" in sig.parameters


def test_get_cache_status_empty_initially():
    reset_cache_global()
    status = get_cache_status()
    assert status["agents_cache_count"] == 0
    assert status["sessions_cache_count"] == 0
    assert status["agent_models"] == []
    assert status["sessions"] == []


def test_check_individual_session_cache_exists_false_when_empty():
    reset_cache_global()
    assert check_individual_session_cache_exists("pytest-thread-unknown") is False
