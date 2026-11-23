"""Seed a conversation thread with a first assistant message."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from jarvis.agents.checkpointer import open_model_checkpointer
from jarvis.agents.graph import compile_tool_agent
from jarvis.agents.session.cache import get_sessions_cache, reset_session
from jarvis.core.config import DEFAULT_MODEL
from jarvis.core.enums import ModelEnum
from jarvis.domain.chat.chat_state import ChatState


class _SeedLLM:
    """Minimal chat-model stand-in used only to compile a graph for seeding."""

    def bind_tools(self, tools: list) -> "_SeedLLM":
        """Ignore tools and return self."""
        return self

    def invoke(self, messages: list) -> AIMessage:
        """Unused: seeding writes state via ``update_state``, not invoke."""
        return AIMessage(content="")


def seed_assistant_message(
    thread_id: str,
    content: str,
    *,
    real_name: str,
    model: ModelEnum = DEFAULT_MODEL,
    reset_first: bool = True,
) -> None:
    """
    Reset (optional) and seed a thread with a single assistant message.

    Used after a periodic task run so the task chat opens with the latest
    report as Jarvis's first message.

    Args:
        thread_id: Target conversation thread.
        content: Assistant message body (the run report).
        real_name: Owner ``real_name`` stored on graph state.
        model: Checkpoint / model file to write into.
        reset_first: When True, clear cache + checkpoint before seeding.

    Returns:
        None.
    """
    text = (content or "").strip() or "(No report produced for this run.)"
    if reset_first:
        reset_session(thread_id, model=model)
    opened = open_model_checkpointer(model)
    try:
        graph, _saver = compile_tool_agent(
            _SeedLLM(), [], checkpointer=opened.saver
        )
        config = {"configurable": {"thread_id": thread_id}}
        graph.update_state(
            config,
            {
                "messages": [AIMessage(content=text)],
                "real_name": real_name,
            },
            as_node="chatbot",
        )
    finally:
        opened.close()
    # Drop any stale in-memory session so the next ask restores INITIALIZED.
    get_sessions_cache().pop((model, thread_id), None)


def mark_session_initialized_if_cached(
    thread_id: str, model: ModelEnum = DEFAULT_MODEL
) -> None:
    """
    If a JarvisSession is cached for the thread, mark it INITIALIZED.

    Args:
        thread_id: Conversation thread.
        model: Model key for the session cache.

    Returns:
        None.
    """
    session = get_sessions_cache().get((model, thread_id))
    if session is not None and hasattr(session, "_chat_state"):
        session._chat_state = ChatState.INITIALIZED  # noqa: SLF001
