"""Shim de entrada Gradio (Hugging Face: app_file: app.py)."""

from interfaces.gradio_app import demo

if __name__ == "__main__":
    demo.launch()
