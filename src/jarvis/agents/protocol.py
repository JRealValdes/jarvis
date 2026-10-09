"""Structural contract shared by Jarvis agent implementations."""

from typing import Any, Protocol

from langgraph.checkpoint.memory import MemorySaver

from jarvis.core.enums import ModelEnum


class JarvisAgent(Protocol):
    """
    Agent the session layer can invoke without knowing the concrete class.

    Attributes:
        model_enum: Model this agent was built for.
        graph: Compiled LangGraph.
        memory: Checkpointer for per-thread history, when the agent persists turns.
        tools: Tools bound into the graph.
    """

    model_enum: ModelEnum
    graph: Any
    memory: MemorySaver | None
    tools: list

    def invoke(self, **kwargs: Any) -> dict:
        """Run one synchronous graph turn."""

    async def ainvoke(self, **kwargs: Any) -> dict:
        """Run one graph turn on the caller's event loop."""

    def cleanup(self) -> None:
        """Release resources owned by this agent instance."""
