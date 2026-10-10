"""Structural contract shared by Jarvis agent implementations."""

from typing import Any, Protocol

from jarvis.core.enums import ModelEnum


class ConversationMemory(Protocol):
    """Checkpointer surface the session layer uses to drop a thread."""

    def delete_thread(self, thread_id: str) -> None:
        """Delete every stored checkpoint for ``thread_id``."""


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
    memory: ConversationMemory | None
    tools: list

    async def invoke(self, **kwargs: Any) -> dict:
        """Run one graph turn (delegates to LangGraph ``ainvoke``)."""

    def cleanup(self) -> None:
        """Release resources owned by this agent instance."""
