"""In-memory caches for agents and chat sessions."""

import asyncio

from jarvis.agents.checkpointer import clear_all_checkpoints, delete_persisted_thread
from jarvis.agents.mcp_session import get_mcp_tool_session
from jarvis.agents.protocol import JarvisAgent
from jarvis.core.config import DEFAULT_MODEL
from jarvis.core.enums import ModelEnum

_sessions_cache: dict[tuple[ModelEnum, str], object] = {}
_agents_cache: dict[ModelEnum, JarvisAgent] = {}


def get_sessions_cache() -> dict[tuple[ModelEnum, str], object]:
    """Return the global sessions cache (mutable)."""
    return _sessions_cache


def get_agents_cache() -> dict[ModelEnum, JarvisAgent]:
    """Return the global agents cache (mutable)."""
    return _agents_cache


def invalidate_agents_cache() -> None:
    """
    Close and drop cached agents so the next turn rebuilds them.

    Keeps chat sessions and checkpoint files. Used when MCP reconnects and
    the compiled graphs still hold tools from the dead stdio session.

    Returns:
        None.
    """
    for agent in _agents_cache.values():
        agent.cleanup()
    _agents_cache.clear()


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
    Remove the cached session and the persisted checkpoint thread.

    Args:
        thread_id: Thread to clear.
        model: Model associated with the thread.

    Returns:
        None.
    """
    session_key = (model, thread_id)
    agent = _agents_cache.get(model)
    if agent is not None and agent.memory is not None:
        agent.memory.delete_thread(thread_id)
    else:
        delete_persisted_thread(model, thread_id)
    _sessions_cache.pop(session_key, None)


def _drop_cached_agents() -> None:
    """Close cached agents, drop sessions, and delete checkpoint files."""
    for agent in _agents_cache.values():
        agent.cleanup()
    _agents_cache.clear()
    _sessions_cache.clear()
    clear_all_checkpoints()


def reset_cache() -> None:
    """
    Clear agent and session caches and delete persisted checkpoints.

    Closes the MCP tool session when it is connected and this thread is not
    already inside a running event loop. On a running loop, use
    ``areset_cache`` so the session is closed on the loop that opened it.

    Returns:
        None.

    Raises:
        RuntimeError: If the MCP session is open on the current running loop.
    """
    _drop_cached_agents()
    session = get_mcp_tool_session()
    if not session.is_connected:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(session.aclose())
        return
    raise RuntimeError(
        "MCP session is open on a running event loop. Use areset_cache()."
    )


async def areset_cache() -> None:
    """
    Clear agent and session caches, delete persisted checkpoints, and close MCP.

    Returns:
        None. Safe when MCP was never connected.
    """
    _drop_cached_agents()
    await get_mcp_tool_session().aclose()
