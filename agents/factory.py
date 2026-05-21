"""LangGraph agent factory by selected model."""

from enums.core_enums import ModelEnum
from agents.jarvis_memory_agent import JarvisMemoryAgent
from agents.jarvis_mcp_memory_agent import JarvisMcpMemoryAgent
from agents.jarvis_basic_agent import JarvisBasicAgent
from config import USE_MCP

models_with_memory: list[ModelEnum] = [ModelEnum.GPT_3_5]
"""Models that persist conversation history with a checkpointer."""


def build_agent(model_used: ModelEnum) -> JarvisBasicAgent | JarvisMemoryAgent | JarvisMcpMemoryAgent:
    """
    Build and instantiate the agent for the given model.

    Args:
        model_used: ModelEnum member (GPT_3_5, ZEPHYR, MISTRAL, etc.).

    Returns:
        Instance of JarvisBasicAgent, JarvisMemoryAgent, or JarvisMcpMemoryAgent.

    Raises:
        ValueError: If the model is not supported.
    """
    if model_used in [ModelEnum.ZEPHYR, ModelEnum.MISTRAL]:
        return JarvisBasicAgent(model_used)
    if model_used == ModelEnum.GPT_3_5:
        if USE_MCP:
            return JarvisMcpMemoryAgent(model_used)
        return JarvisMemoryAgent(model_used)
    raise ValueError("Modelo no soportado.")
