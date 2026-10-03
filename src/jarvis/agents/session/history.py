"""Parse LangChain message history for API / UI consumers."""

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from jarvis.agents.session.cache import get_sessions_cache
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


def get_message_history(
    thread_id: str, model: ModelEnum = DEFAULT_MODEL
) -> list[dict]:
    """
    Return parsed message history for a thread if the session is cached.

    Args:
        thread_id: Conversation identifier.
        model: Cached agent model.

    Returns:
        List of ``{role, content}`` messages; empty if no session or on failure.
    """
    sessions_cache = get_sessions_cache()
    logger.debug("Sessions cache: %s", sessions_cache)
    session_key = (model, thread_id)
    if session_key not in sessions_cache:
        logger.warning(
            "No session found for thread %s with model %s", thread_id, model.name
        )
        return []
    try:
        agent = sessions_cache[session_key].agent
        last_snapshot = list(
            agent.graph.get_state_history({"configurable": {"thread_id": thread_id}})
        )[0]
        messages = last_snapshot.values.get("messages", [])
        return parse_message_list(messages)
    except Exception as e:
        logger.error(
            "Failed to retrieve message history for thread %s: %s", thread_id, e
        )
        return []
