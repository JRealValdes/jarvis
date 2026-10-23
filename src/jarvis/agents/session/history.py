"""Parse LangChain message history for API / UI consumers."""

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from jarvis.agents.checkpointer import checkpoint_path, open_model_checkpointer
from jarvis.agents.session.cache import get_agents_cache
from jarvis.core.config import DEFAULT_MODEL, SHOW_TOOL_TRACES
from jarvis.core.enums import ModelEnum

logger = logging.getLogger(__name__)


def _has_visible_content(content: Any) -> bool:
    """Return whether assistant content is worth showing in chat.

    Args:
        content: LangChain message content, either text or structured blocks.

    Returns:
        False for missing, empty, or whitespace-only text. True when there
        is any other non-empty value.
    """
    if isinstance(content, str):
        return bool(content.strip())
    return bool(content)


def _format_tool_call(name: str, args: dict[str, Any]) -> str:
    """Format one tool call the way chat traces name it.

    Args:
        name: Tool name.
        args: Parsed arguments. Empty when the call has none.

    Returns:
        One assistant sentence with the tool name and its arguments.
    """
    if args:
        args_str = ", ".join(f"{key}={value}" for key, value in args.items())
        return f"Calling function: {name}. Arguments: {args_str}"
    return f"Calling function: {name}. No arguments."


def _tool_calls_for_display(msg: AIMessage) -> list[tuple[str, dict[str, Any]]]:
    """Collect tool calls from the message attribute or legacy kwargs.

    Current LangChain stores calls on ``AIMessage.tool_calls`` as
    ``{name, args}`` and often leaves ``additional_kwargs`` empty, with
    ``content`` equal to ``""``. Older messages only set
    ``additional_kwargs["tool_calls"]`` in the OpenAI function shape.
    When both are present, the attribute wins so one call is not announced
    twice.

    Args:
        msg: Assistant message that may request tools.

    Returns:
        ``(name, args)`` pairs. Empty when the message is not a tool turn.
        Legacy arguments that are not JSON become an empty mapping so the
        turn is still recognized and is not copied as a blank reply.
    """
    native = list(getattr(msg, "tool_calls", None) or [])
    if native:
        calls: list[tuple[str, dict[str, Any]]] = []
        for call in native:
            if isinstance(call, dict):
                name = str(call.get("name") or "")
                args = call.get("args") or {}
            else:
                name = str(getattr(call, "name", "") or "")
                args = getattr(call, "args", None) or {}
            if not isinstance(args, dict):
                args = {}
            calls.append((name, args))
        return calls

    raw = msg.additional_kwargs.get("tool_calls") or []
    calls: list[tuple[str, dict[str, Any]]] = []
    for tool_call in raw:
        function = tool_call.get("function") or {}
        name = str(function.get("name") or "")
        arguments = function.get("arguments") or "{}"
        if isinstance(arguments, dict):
            args = arguments
        else:
            try:
                parsed = json.loads(arguments)
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            args = parsed if isinstance(parsed, dict) else {}
        calls.append((name, args))
    return calls


def parse_message_list(
    messages: list,
    *,
    show_tool_traces: bool | None = None,
) -> list[dict]:
    """
    Convert LangChain messages to ``{role, content}`` dicts for the API.

    When ``show_tool_traces`` is False (the default via config), tool call
    announcements and tool results are omitted so the UI only shows the
    final assistant replies. A tool-call ``AIMessage`` with no visible text
    is dropped entirely. Calls are read from ``tool_calls`` or, for older
    messages, from ``additional_kwargs["tool_calls"]``. Enable
    ``JARVIS_SHOW_TOOL_TRACES`` (or pass ``True``) to paint every tool the
    same way. For full agent/tool inspection without chat noise, use
    LangSmith tracing (see README).

    Args:
        messages: List of SystemMessage, HumanMessage, AIMessage, ToolMessage.
        show_tool_traces: Whether to include tool call/result messages.
            ``None`` uses ``SHOW_TOOL_TRACES`` from config.

    Returns:
        List of dicts with roles ``system``, ``user``, or ``assistant``.
    """
    include_tools = (
        SHOW_TOOL_TRACES if show_tool_traces is None else show_tool_traces
    )
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            tool_calls = _tool_calls_for_display(msg)
            if tool_calls and include_tools:
                for name, args in tool_calls:
                    result.append(
                        {
                            "role": "assistant",
                            "content": _format_tool_call(name, args),
                        }
                    )
            elif _has_visible_content(msg.content):
                result.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            if include_tools:
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

    Uses the live agent graph when that model is already cached and this
    call is not on the loop that owns the async checkpointer. ``get_state``
    on ``AsyncSqliteSaver`` fails on that loop, so a running loop reads the
    checkpoint file instead. After a restart, reads the file directly.

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
    if _can_read_live_graph(agent):
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


def _can_read_live_graph(agent: object | None) -> bool:
    """
    Report whether ``agent.graph.get_state`` is safe to call.

    Args:
        agent: Cached agent, or None when this model has no live graph.

    Returns:
        True when the agent has a compiled graph and the caller is not on
        a running event loop. False when the graph is not open yet, or when
        the caller is on the loop that owns ``AsyncSqliteSaver``.
    """
    if agent is None or getattr(agent, "graph", None) is None:
        return False
    if getattr(agent, "memory", None) is None:
        return False
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return True
    return False


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
