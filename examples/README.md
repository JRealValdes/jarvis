# Examples (experimental)

Scripts and notebooks here are **not** part of the installed `jarvis` package. They are for learning and spikes.

## How to run

From the repository root, with dependencies installed (`uv sync`).

Notebooks: open in Jupyter/VS Code with the project `.venv` kernel.

## Fixtures

Sample audio and documents for future STT / RAG work live under [`fixtures/`](fixtures/).

## Google Calendar OAuth

Place credentials under `data/google/<username>/<account>/` (see `data/google/example_user/`). Use `examples/google_api_demo.ipynb` for the interactive OAuth flow.

## Job / LinkedIn reply preferences

Copy [`data/users/example_user/job_preferences.yaml`](../data/users/example_user/job_preferences.yaml) to `data/users/<your_real_name>/job_preferences.yaml` and edit. Jarvis uses this file when drafting LinkedIn replies (`draft_linkedin_reply_tool`).
