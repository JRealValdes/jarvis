"""Factoría de agentes LangGraph según el modelo seleccionado."""

from enums.core_enums import ModelEnum
from agents.jarvis_memory_agent import JarvisMemoryAgent
from agents.jarvis_mcp_memory_agent import JarvisMcpMemoryAgent
from agents.jarvis_basic_agent import JarvisBasicAgent
from config import USE_MCP

models_with_memory: list[ModelEnum] = [ModelEnum.GPT_3_5]
"""Modelos que persisten historial de conversación con checkpointer."""


def build_agent(model_used: ModelEnum) -> JarvisBasicAgent | JarvisMemoryAgent | JarvisMcpMemoryAgent:
    """
    Construye e instancia el agente adecuado para el modelo indicado.

    Args:
        model_used: Miembro de ModelEnum (GPT_3_5, ZEPHYR, MISTRAL, etc.).

    Returns:
        Instancia de JarvisBasicAgent, JarvisMemoryAgent o JarvisMcpMemoryAgent.

    Raises:
        ValueError: Si el modelo no está soportado.
    """
    if model_used in [ModelEnum.ZEPHYR, ModelEnum.MISTRAL]:
        return JarvisBasicAgent(model_used)
    if model_used == ModelEnum.GPT_3_5:
        if USE_MCP:
            return JarvisMcpMemoryAgent(model_used)
        return JarvisMemoryAgent(model_used)
    raise ValueError("Modelo no soportado.")
