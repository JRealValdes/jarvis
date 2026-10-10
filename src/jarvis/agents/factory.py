"""LangGraph agent factory by selected model."""

from jarvis.agents.implementations.memory import JarvisMemoryAgent
from jarvis.agents.mcp_session import get_mcp_tool_session
from jarvis.agents.protocol import JarvisAgent
from jarvis.core.config import USE_MCP
from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import is_openai_chat_model
from jarvis.tools import local_tools


def build_agent(model_used: ModelEnum) -> JarvisAgent:
    """
    Build the agent for the given model.

    When ``USE_MCP`` is set, the process-wide MCP session must already be
    connected. The returned agent implements ``JarvisAgent``; new
    implementations do not change this signature.

    Args:
        model_used: OpenAI chat ModelEnum member (GPT_4O_MINI, GPT_3_5).

    Returns:
        Agent ready for ``ainvoke``.

    Raises:
        ValueError: If the model is not an OpenAI chat model.
        RuntimeError: If MCP is enabled and the tool session is not connected.
    """
    if not is_openai_chat_model(model_used):
        raise ValueError(f"Unsupported model: {model_used}.")

    tools = list(local_tools)
    if USE_MCP:
        session = get_mcp_tool_session()
        if not session.is_connected:
            raise RuntimeError(
                "MCP is enabled but the tool session is not connected. "
                "Open it from the API lifespan, the CLI, or ask_jarvis "
                "before building an agent."
            )
        tools.extend(session.tools)
    return JarvisMemoryAgent(model_used, tools=tools)
