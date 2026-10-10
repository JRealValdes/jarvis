"""Parse LangChain message history for API / UI consumers."""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from jarvis.agents.checkpointer import checkpoint_path, open_model_checkpointer
from jarvis.agents.session.cache import get_agents_cache
from jarvis.core.config import DEFAULT_MODEL
from jarvis.core.enums import ModelEnum

logger = logging.getLogger(__name__)

NOT_VERBOSED_TOOLS = ["get_upcoming_events_tool"]


def parse_message_list(messages: list) -> list[dict]:
    """
    Convert LangChain messages to ``{role, content}`` dicts for the API.

    Args:
        messages: List of SystemMessage, HumanMessage, AIMessage, ToolMessage.

    Returns:
        List of dicts with roles ``system``, ``user``, or ``assistant``.
    """
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            if "tool_calls" in msg.additional_kwargs:
                for tool_call in msg.additional_kwargs["tool_calls"]:
                    args_dict = json.loads(tool_call["function"]["arguments"])
                    args_str = ", ".join(
                        f"{key}={value}" for key, value in args_dict.items()
                    )
                    if args_str:
                        result.append(
                            {
                                "role": "assistant",
                                "content": (
                                    f"Calling function: {tool_call['function']['name']}. "
                                    f"Arguments: {args_str}"
                                ),
                            }
                        )
                    else:
                        result.append(
                            {
                                "role": "assistant",
                                "content": (
                                    f"Calling function: {tool_call['function']['name']}. "
                                    "No arguments."
                                ),
                            }
                        )
            else:
                result.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            if msg.name not in NOT_VERBOSED_TOOLS or "error" in msg.content.lower():
                result.append(
                    {
                        "role": "assistant",
                        "content": f"Function result {msg.name}: {msg.content}",
                    }
                )
    return result


def _snapshot_from_values(values: dict[str, Any]) -> dict[str, Any] | None:
    """
    Build a thread snapshot from checkpoint channel values.

    Args:
        values: Checkpoint ``channel_values`` or graph state values.

    Returns:
        Dict with ``messages`` and ``real_name``, or None when the thread
        has no messages yet.
    """
    messages = values.get("messages") or []
    if not messages:
        return None
    real_name = values.get("real_name") or ""
    if not isinstance(real_name, str):
        real_name = ""
    return {"messages": list(messages), "real_name": real_name}


def load_thread_snapshot(model: ModelEnum, thread_id: str) -> dict[str, Any] | None:
    """
    Load the latest checkpoint for a thread.

    Uses the live agent graph when that model is already cached, so history
    matches in-process state and a second SQLite connection is not opened.
    After a restart, reads the model checkpoint file directly.

    Args:
        model: Model whose checkpoint file stores the thread.
        thread_id: Conversation id.

    Returns:
        Dict with ``messages`` and ``real_name``, or None when the thread
        has no stored messages.

    Raises:
        OSError: If an existing checkpoint file cannot be opened.
        Exception: If the checkpointer cannot decode the thread.
    """
    agent = get_agents_cache().get(model)
    config = {"configurable": {"thread_id": thread_id}}
    if agent is not None and getattr(agent, "memory", None) is not None:
        snapshot = agent.graph.get_state(config)
        values = snapshot.values if isinstance(snapshot.values, dict) else {}
        return _snapshot_from_values(values)

    path = checkpoint_path(model)
    if not path.exists():
        return None
    opened = open_model_checkpointer(model)
    try:
        saved = opened.saver.get_tuple(config)
    finally:
        opened.close()
    if saved is None:
        return None
    values = saved.checkpoint.get("channel_values") or {}
    if not isinstance(values, dict):
        return None
    return _snapshot_from_values(values)


def get_message_history(
    thread_id: str, model: ModelEnum = DEFAULT_MODEL
) -> list[dict]:
    """
    Return parsed message history for a thread from the checkpointer.

    Args:
        thread_id: Conversation identifier.
        model: Model whose checkpoint file stores the thread.

    Returns:
        List of ``{role, content}`` messages. Empty when the thread has no
        checkpoint or the checkpoint cannot be read.
    """
    try:
        snapshot = load_thread_snapshot(model, thread_id)
    except Exception as e:
        logger.error(
            "Failed to retrieve message history for thread %s: %s", thread_id, e
        )
        return []
    if snapshot is None:
        return []
    return parse_message_list(snapshot["messages"])
