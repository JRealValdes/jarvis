"""LangGraph agent factory by selected model."""

from jarvis.agents.implementations import (
    JarvisBasicAgent,
    JarvisMcpMemoryAgent,
    JarvisMemoryAgent,
)
from jarvis.core.config import USE_MCP
from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import is_openai_chat_model

models_with_memory: list[ModelEnum] = [
    ModelEnum.GPT_3_5,
    ModelEnum.GPT_4O_MINI,
]
"""Models that persist conversation history with a checkpointer."""


def build_agent(
    model_used: ModelEnum,
) -> JarvisBasicAgent | JarvisMemoryAgent | JarvisMcpMemoryAgent:
    """
    Build and instantiate the agent for the given model.

    Args:
        model_used: ModelEnum member (GPT_4O_MINI, GPT_3_5, ZEPHYR, MISTRAL, etc.).

    Returns:
        Instance of JarvisBasicAgent, JarvisMemoryAgent, or JarvisMcpMemoryAgent.

    Raises:
        ValueError: If the model is not supported.
    """
    if model_used in [ModelEnum.ZEPHYR, ModelEnum.MISTRAL]:
        return JarvisBasicAgent(model_used)
    if is_openai_chat_model(model_used):
        if USE_MCP:
            return JarvisMcpMemoryAgent(model_used)
        return JarvisMemoryAgent(model_used)
    raise ValueError("Unsupported model.")
