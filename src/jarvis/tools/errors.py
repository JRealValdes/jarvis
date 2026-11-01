"""Shared formatting for tool failures surfaced to the LLM."""

from __future__ import annotations

MAX_REASON_CHARS = 500

_DEFAULT_HINT = (
    "Explain briefly what happened to the user and what they can try next "
    "(retry, rephrase, or a different request). "
    "Do not invent successful results or data."
)


def format_tool_failure(
    *,
    what: str,
    reason: str | None = None,
    hint: str | None = None,
) -> str:
    """
    Build an LLM-facing tool error string.

    Args:
        what: Short description of what failed (e.g. ``Image generation``).
        reason: Optional plain-language cause.
        hint: Optional instruction for the model; a default explain/retry hint
            is used when omitted.

    Returns:
        Single string suitable as tool result / ``ToolMessage`` content.
    """
    label = what.strip().rstrip(".") or "The tool"
    parts = [f"{label} failed."]
    if reason:
        cleaned = " ".join(str(reason).split())
        if len(cleaned) > MAX_REASON_CHARS:
            cleaned = cleaned[: MAX_REASON_CHARS - 1] + "…"
        parts.append(cleaned)
    parts.append(hint or _DEFAULT_HINT)
    return " ".join(parts)


def handle_tool_node_error(exc: Exception) -> str:
    """
    Convert a raised tool exception into ``ToolMessage`` content for the model.

    Used as ``ToolNode(handle_tool_errors=...)`` so the chatbot node still runs
    after a tool raises (builtins, MCP, unexpected errors).

    Args:
        exc: Exception raised while executing a tool.

    Returns:
        Instructional error string for the next chatbot turn.
    """
    from langgraph.prebuilt.tool_node import ToolInvocationError

    if isinstance(exc, ToolInvocationError):
        return format_tool_failure(what="Tool call", reason=exc.message)

    message = getattr(exc, "message", None)
    if not isinstance(message, str) or not message.strip():
        message = str(exc).strip() or type(exc).__name__
    reason = f"{type(exc).__name__}: {message}"
    return format_tool_failure(what="The tool", reason=reason)
