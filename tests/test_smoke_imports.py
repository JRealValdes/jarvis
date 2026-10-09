"""Smoke tests: core modules import and public session API is callable."""

import inspect
from unittest.mock import MagicMock, patch

from jarvis.agents.factory import build_agent
from jarvis.agents.session import (
    aask_jarvis,
    ask_jarvis,
    check_individual_session_cache_exists,
    get_cache_status,
    reset_cache,
)
from jarvis.core.config import DEFAULT_MODEL
from jarvis.core.enums import IdentificationFailedProtocolEnum, ModelEnum


def test_model_enum_members():
    assert ModelEnum.GPT_4O_MINI.value == "gpt_4o_mini"
    assert ModelEnum.GPT_3_5.value == "chatgpt_3_5"
    assert len(ModelEnum) == 2


def test_identification_failed_protocol_enum():
    assert IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE.value == "automatic_response"


def test_default_model_is_gpt_35():
    assert DEFAULT_MODEL == ModelEnum.GPT_4O_MINI


@patch("jarvis.agents.implementations.memory.ChatOpenAI")
def test_build_agent_factory_returns_object(mock_chat_openai: MagicMock):
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    mock_chat_openai.return_value = fake_llm

    agent = build_agent(ModelEnum.GPT_4O_MINI)

    assert callable(agent.invoke)
    assert callable(agent.ainvoke)
    assert callable(agent.cleanup)
    assert agent.memory is not None


def test_ask_jarvis_is_callable():
    assert callable(ask_jarvis)
    assert callable(aask_jarvis)
    sig = inspect.signature(ask_jarvis)
    assert "prompt" in sig.parameters
    assert "thread_id" in sig.parameters


def test_get_cache_status_empty_initially():
    reset_cache()
    status = get_cache_status()
    assert status["agents_cache_count"] == 0
    assert status["sessions_cache_count"] == 0
    assert status["agent_models"] == []
    assert status["sessions"] == []


def test_check_individual_session_cache_exists_false_when_empty():
    reset_cache()
    assert check_individual_session_cache_exists("pytest-thread-unknown") is False
