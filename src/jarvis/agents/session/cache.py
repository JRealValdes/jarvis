"""In-memory caches for agents and chat sessions."""

from jarvis.core.config import DEFAULT_MODEL
from jarvis.core.enums import ModelEnum

_sessions_cache: dict[tuple[ModelEnum, str], object] = {}
_agents_cache: dict[ModelEnum, object] = {}


def get_sessions_cache() -> dict[tuple[ModelEnum, str], object]:
    """Return the global sessions cache (mutable)."""
    return _sessions_cache


def get_agents_cache() -> dict[ModelEnum, object]:
    """Return the global agents cache (mutable)."""
    return _agents_cache


def get_cache_status() -> dict:
    """
    Summarize global agent and session cache state.

    Returns:
        Dict with keys ``agents_cache_count``, ``sessions_cache_count``,
        ``agent_models`` (names), and ``sessions`` (model/thread pairs).
    """
    sessions = [(key[0].name, key[1]) for key in _sessions_cache.keys()]
    return {
        "agents_cache_count": len(_agents_cache),
        "sessions_cache_count": len(_sessions_cache),
        "agent_models": [model.name for model in _agents_cache.keys()],
        "sessions": list(map(str, sessions)),
    }


def check_individual_session_cache_exists(
    thread_id: str, model: ModelEnum = DEFAULT_MODEL
) -> bool:
    """
    Report whether a session is cached for the given thread and model.

    Args:
        thread_id: Conversation id (e.g. user real_name).
        model: Model associated with the session.

    Returns:
        True if key (model, thread_id) is in the cache.
    """
    return (model, thread_id) in _sessions_cache


def reset_session(thread_id: str, model: ModelEnum = DEFAULT_MODEL) -> None:
    """
    Remove the cached session and agent memory thread if applicable.

    Args:
        thread_id: Thread to clear.
        model: Model associated with the thread.

    Returns:
        None.
    """
    session_key = (model, thread_id)
    agent = _agents_cache.get(model)
    if agent and hasattr(agent, "memory") and agent.memory:
        agent.memory.delete_thread(thread_id)
    _sessions_cache.pop(session_key, None)


def reset_cache_global() -> None:
    """
    Clear agent and session caches completely.

    Returns:
        None.
    """
    _agents_cache.clear()
    _sessions_cache.clear()


reset_cache = reset_cache_global
"""Alias used by the Gradio UI."""
