"""LangGraph agent with memory (MemorySaver) and tools for OpenAI chat models."""

from typing import Any

from langchain_openai import ChatOpenAI

from jarvis.agents.graph import compile_tool_agent
from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import resolve_openai_chat_model_id
from jarvis.tools import local_tools


class JarvisMemoryAgent:
    """
    Agent with a chatbot ↔ tools loop and an in-memory checkpointer.

    MCP tools, when enabled, are passed in by the factory. This class does not
    open or close the process-wide MCP session.

    Attributes:
        model_enum: OpenAI-backed ModelEnum (e.g. GPT_4O_MINI, GPT_3_5).
        graph: Compiled graph.
        memory: MemorySaver for per-thread_id threads.
        tools: Tools bound into the graph.
    """

    def __init__(self, model_enum: ModelEnum, tools: list | None = None) -> None:
        """
        Args:
            model_enum: OpenAI chat ModelEnum member.
            tools: Tools to bind. Defaults to the local tool registry.

        Raises:
            ValueError: If the model is not an OpenAI chat model.
        """
        self.model_enum = model_enum
        self.tools = list(local_tools if tools is None else tools)
        llm = ChatOpenAI(
            model=resolve_openai_chat_model_id(model_enum),
            temperature=0,
        )
        self.graph, self.memory = compile_tool_agent(llm, self.tools)

    def invoke(self, **kwargs: Any) -> dict:
        """
        Invoke the graph (requires config with thread_id when memory is enabled).

        Args:
            **kwargs: ``input``, ``config``, etc.

        Returns:
            Final graph state.
        """
        return self.graph.invoke(**kwargs)

    async def ainvoke(self, **kwargs: Any) -> dict:
        """
        Invoke the graph on the caller's event loop.

        Args:
            **kwargs: ``input``, ``config``, etc.

        Returns:
            Final graph state.
        """
        return await self.graph.ainvoke(**kwargs)

    def cleanup(self) -> None:
        """Release agent resources. Does not close the shared MCP session."""
        return None
