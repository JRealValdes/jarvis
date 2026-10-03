"""Interactive Jarvis CLI (stdin read loop)."""

from jarvis.core.config import DEFAULT_MODEL
from jarvis.agents.session import ask_jarvis

model_used = DEFAULT_MODEL
thread_id = "1"

_EXIT_COMMANDS = {"exit", "quit", "salir"}
_FAREWELL_MARKERS = ("that's all", "eso es todo")


def main() -> None:
    """
    Run console chat until exit/quit/salir or a farewell phrase with ``jarvis``.

    Returns:
        None.
    """
    while True:
        question = input("User: ")
        lowered = question.lower()
        if lowered in _EXIT_COMMANDS or (
            "jarvis" in lowered and any(marker in lowered for marker in _FAREWELL_MARKERS)
        ):
            break
        response = ask_jarvis(question, model_used, thread_id=thread_id)
        for response_msg in response:
            print("Jarvis:", response_msg)
