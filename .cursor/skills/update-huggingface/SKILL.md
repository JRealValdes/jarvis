---
name: update-huggingface
description: >-
  Refresh requirements.txt via uv export, commit if it changed, and push the
  Jarvis app to the Hugging Face Space remote. Use when the user asks to update
  Hugging Face, deploy to the Space, sync HF, push to spaces/JRealValdes/jarvis,
  or run the update-huggingface skill.
---

# Update Hugging Face Space

Deploy the current Jarvis tree to the Hugging Face Space and keep the pip export in sync for Spaces installs.

## Target

| Item | Value |
|------|--------|
| Space URL | https://huggingface.co/spaces/JRealValdes/jarvis |
| Git remote | `space` (`https://huggingface.co/spaces/JRealValdes/jarvis`) |
| Deploy ref | Push `HEAD` to Space `main` (`git push space HEAD:main`) |

If remote `space` is missing, add it:

```bash
git remote add space https://huggingface.co/spaces/JRealValdes/jarvis
```

## Workflow

Copy and track:

```
Progress:
- [ ] 1. Export requirements.txt
- [ ] 2. Commit export if changed
- [ ] 3. Push to Space main
- [ ] 4. Report Space URL + result
```

### 1. Export requirements

From the repo root (uv project):

```bash
uv export --no-dev -o requirements.txt
```

Do not hand-edit `requirements.txt`. Source of truth remains `pyproject.toml` / `uv.lock`.

### 2. Commit if the export changed

```bash
git status -- requirements.txt
git diff -- requirements.txt
```

- If **no** changes to `requirements.txt`: skip commit; say so.
- If changed: stage **only** `requirements.txt` and commit (this skill authorizes that commit):

```bash
git add requirements.txt
git commit -m "chore: refresh requirements.txt for Hugging Face Spaces"
```

Follow the usual git safety rules otherwise (no force, no hook skip, no amend unless the standard amend conditions apply). Do not include unrelated files.

### 3. Push to Hugging Face

```bash
git push space HEAD:main
```

- Push the **current** `HEAD` (whatever branch/commit is checked out), mapped to Space `main` (what Spaces builds).
- Do **not** `git push --force` to `space` unless the user explicitly asks.
- Do **not** push secrets (`.env`, `*secret*`, credentials under `data/`). Rely on `.gitignore`.

If auth fails, tell the user to log in to Hugging Face (`huggingface-cli login` or git credential) and retry; do not invent tokens.

### 4. Report

Briefly state:

1. Whether `requirements.txt` was regenerated and committed
2. Whether the push succeeded
3. Space URL: https://huggingface.co/spaces/JRealValdes/jarvis

## Notes

- Root `app.py` remains the Gradio entry for Spaces (`app_file` in the README YAML).
- Local day-to-day use stays on uv (`uv sync`, `uv run jarvis …`); the export exists for the Space pip installer.
- Prefer English commit messages (Conventional Commits).
