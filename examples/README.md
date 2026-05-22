# Examples (experimental)

Scripts and notebooks here are **not** part of the installed `jarvis` package. They are for learning and spikes.

## How to run

From the repository root, with dependencies installed (`uv sync`):

```bash
uv run python examples/chatbot_with_tools.py
uv run python examples/basic_mcp_test.py
```

Notebooks: open in Jupyter/VS Code with the project `.venv` kernel.

## Google Calendar OAuth

Place credentials under `data/google/<username>/<account>/` (see `data/google/example_user/`). Use `examples/google_api_demo.ipynb` for the interactive OAuth flow.
