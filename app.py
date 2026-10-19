"""Gradio entry for Hugging Face Spaces (``app_file: app.py``). Prefer ``uv run jarvis ui`` locally.

Imports ``jarvis.core.config`` first so ``.env`` loads before the UI.
"""

import jarvis.core.config  # noqa: F401  # load .env once before the Gradio app

from jarvis.interfaces.gradio_app import demo

if __name__ == "__main__":
    demo.launch()
