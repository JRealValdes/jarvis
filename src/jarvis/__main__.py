"""Unified CLI: ``uv run jarvis chat|api|ui``."""

from __future__ import annotations

import argparse
import sys


def _run_chat() -> None:
    from jarvis.interfaces.cli import main as chat_main

    chat_main()


def _run_api() -> None:
    from jarvis.api.app import main as api_main

    api_main()


def _run_ui() -> None:
    from jarvis.interfaces.gradio_app import demo

    demo.launch()


def main(argv: list[str] | None = None) -> None:
    """
    Dispatch to chat, API, or Gradio UI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).
    """
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis personal AI - choose how to run it.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("chat", help="Interactive console chatbot")
    sub.add_parser("api", help="HTTP API (FastAPI + uvicorn)")
    sub.add_parser("ui", help="Gradio web UI")

    args = parser.parse_args(argv)

    if args.command == "chat":
        _run_chat()
    elif args.command == "api":
        _run_api()
    elif args.command == "ui":
        _run_ui()
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
