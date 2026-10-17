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

Preferred: ask Jarvis in chat to set up or update your job / LinkedIn reply preferences. It interviews you and writes `data/users/<your_real_name>/job_preferences.yaml` via `save_job_preferences_tool` after you confirm.

Alternatively, copy [`data/users/example_user/job_preferences.yaml`](../data/users/example_user/job_preferences.yaml) and edit by hand. The same file is used by `draft_linkedin_reply_tool`.

Optional style samples: put complete messages you like in [`data/users/example_user/linkedin_reply_examples.yaml`](../data/users/example_user/linkedin_reply_examples.yaml) (copy to your user folder). The draft tool uses them as phrasing/structure references.
