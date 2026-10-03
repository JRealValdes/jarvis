"""Factory / memory-agent wiring for OpenAI models (mocked LLM, no network)."""

from unittest.mock import MagicMock, patch

from jarvis.agents.factory import build_agent, models_with_memory
from jarvis.agents.implementations.memory import JarvisMemoryAgent
from jarvis.core.enums import ModelEnum


def test_models_with_memory_includes_gpt_4o_mini():
    assert ModelEnum.GPT_4O_MINI in models_with_memory
    assert ModelEnum.GPT_3_5 in models_with_memory


@patch("jarvis.agents.implementations.memory.ChatOpenAI")
def test_memory_agent_builds_with_gpt_4o_mini_id(mock_chat_openai: MagicMock):
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    mock_chat_openai.return_value = fake_llm

    agent = JarvisMemoryAgent(ModelEnum.GPT_4O_MINI)

    mock_chat_openai.assert_called_once_with(model="gpt-4o-mini", temperature=0)
    assert agent.model_enum == ModelEnum.GPT_4O_MINI
    assert agent.graph is not None
    assert agent.memory is not None


@patch("jarvis.agents.factory.JarvisMemoryAgent")
def test_build_agent_returns_memory_agent_for_gpt_4o_mini(
    mock_memory_agent: MagicMock,
):
    instance = MagicMock()
    mock_memory_agent.return_value = instance

    result = build_agent(ModelEnum.GPT_4O_MINI)

    mock_memory_agent.assert_called_once_with(ModelEnum.GPT_4O_MINI)
    assert result is instance
