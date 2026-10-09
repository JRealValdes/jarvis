"""Interactive Jarvis CLI (stdin read loop)."""

import asyncio

from jarvis.agents.mcp_session import get_mcp_tool_session
from jarvis.agents.session import aask_jarvis, ask_jarvis
from jarvis.core.config import DEFAULT_MODEL, USE_MCP

model_used = DEFAULT_MODEL
thread_id = "1"

_EXIT_COMMANDS = {"exit", "quit", "salir"}
_FAREWELL_MARKERS = ("that's all", "eso es todo")


def _should_exit(question: str) -> bool:
    """
    Report whether the console loop should stop.

    Args:
        question: Raw line from stdin.

    Returns:
        True for exit/quit/salir or a farewell phrase that mentions Jarvis.
    """
    lowered = question.lower()
    return lowered in _EXIT_COMMANDS or (
        "jarvis" in lowered and any(marker in lowered for marker in _FAREWELL_MARKERS)
    )


def _print_replies(response: list[str]) -> None:
    """
    Print each Jarvis reply line.

    Args:
        response: Reply fragments from the session.
    """
    for response_msg in response:
        print("Jarvis:", response_msg)


def _sync_loop() -> None:
    """
    Run the console chat without MCP.

    Returns:
        None.
    """
    while True:
        question = input("User: ")
        if _should_exit(question):
            break
        _print_replies(ask_jarvis(question, model_used, thread_id=thread_id))


async def _async_loop() -> None:
    """
    Run the console chat on one event loop so the MCP session stays open.

    Returns:
        None. Closes the MCP session when the loop ends.
    """
    await get_mcp_tool_session().aconnect()
    try:
        while True:
            question = await asyncio.to_thread(input, "User: ")
            if _should_exit(question):
                break
            response = await aask_jarvis(question, model_used, thread_id=thread_id)
            _print_replies(response)
    finally:
        await get_mcp_tool_session().aclose()


def main() -> None:
    """
    Run console chat until exit/quit/salir or a farewell phrase with ``jarvis``.

    When MCP is enabled, the whole loop shares one event loop with the stdio
    session. Otherwise each turn uses the synchronous agent path.

    Returns:
        None.
    """
    if USE_MCP:
        asyncio.run(_async_loop())
        return
    _sync_loop()
