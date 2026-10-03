"""Gradio entry for Hugging Face Spaces (``app_file: app.py``). Prefer ``uv run jarvis ui`` locally."""

from jarvis.interfaces.gradio_app import demo

if __name__ == "__main__":
    demo.launch()
