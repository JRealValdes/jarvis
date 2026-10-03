---
title: Jarvis
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.29.1
app_file: app.py
pinned: false
---

# Jarvis Project (Personal AI with Langchain)

"Jarvis"-style AI using LangGraph and Langchain.
Hello, sir. How can I assist you today?

## Requirements
- Python 3.10+
- OpenAI API key (optional)

## Installation

Requirement: [uv](https://docs.astral.sh/uv/) (`pip install uv` or the official installer).

```bash
uv sync --all-groups    # create .venv and install runtime + dev deps (pytest)
```

For deploys that only read `requirements.txt` (e.g. Hugging Face Spaces):

```bash
uv export --no-dev -o requirements.txt
```

Classic install without uv (alternative):

```bash
pip install -r requirements.txt
pip install -e .
```

## How to run

Jarvis has three modes. One CLI dispatches all of them:

| Mode | Command | What it does |
|------|---------|--------------|
| **chat** | `uv run jarvis chat` | Interactive console chatbot |
| **api** | `uv run jarvis api` | HTTP API (FastAPI + uvicorn) |
| **ui** | `uv run jarvis ui` | Gradio web UI |

```bash
uv run jarvis --help
uv run jarvis chat
uv run jarvis api
uv run jarvis ui
```

Hugging Face Spaces still launches Gradio via root `app.py` (`app_file` in the YAML header). Prefer `uv run jarvis ui` locally.

## Development

```bash
uv run pytest
uv run jarvis chat    # or api / ui
```

Docstring convention in production code: module + **Args** / **Returns** / **Raises**.

## Configuration

1. Copy `.env.example` to `.env` and fill in keys you use (OpenAI, HF, Fernet, JWT, optional Telegram/Firebase).
2. Seed users into the local DB (see below).
3. Google Calendar (optional): OAuth files under `data/google/<username>/<account>/` (see `data/google/example_user/`). Interactive flow: `examples/google_api_demo.ipynb`.
4. MCP (optional): edit `data/mcp/server_config.json`; server scripts live under `src/jarvis/mcp/servers/`.
5. Public API tunnel (optional): set `EXPOSE_API_WITH_CLOUDFLARED` in code/env workflow only when you want cloudflared (default is off).

## Local runtime assets (not in git)

These live on each machine and are required (or optional) for a full local setup. Copy/recreate them when moving to a new computer:

| Asset | Path | Required? | How to obtain |
|-------|------|-------------|---------------|
| Environment secrets | `.env` | Yes for real LLM/API use | Copy `.env.example` |
| Users database | `data/users.db` | Yes for identification / API login | Seed with `scripts/users/manage_users.ipynb` from CSV (`example_users_info.csv` / your `secret_users_info.csv`) |
| Google OAuth | `data/google/<user>/<account>/` (`*secret*.json`) | Only for Calendar tools | Google Cloud OAuth client + `examples/google_api_demo.ipynb` |
| Firebase private key | `data/firebase_project_secret_private_key.json` | Only if using Firebase URL share | Firebase console |
| MCP config | `data/mcp/server_config.json` | Only if `USE_MCP` | Tracked example config is in repo; customize locally if needed |

Gitignores cover `.env`, `data/users.db`, and `*secret*` files. Do not commit personal credentials.

## Architecture

Installable package `jarvis` under `src/jarvis/`. Layers: `core`, `domain`, `infrastructure`, `agents` (factory, `session/`, `implementations/`), `tools` (`registry` + `builtins/`), `api`, `interfaces` (CLI + Gradio), `mcp` (server scripts). Runtime assets live in `data/`; seed/admin helpers in `scripts/`; sample media/docs for future STT/RAG under `examples/fixtures/`.

## Structure
```
jarvis/                          # repository root
├── src/jarvis/                  # Python package
│   ├── __main__.py              # uv run jarvis {chat|api|ui}
│   ├── agents/
│   │   ├── factory.py
│   │   ├── session/             # cache, history, orchestrator
│   │   └── implementations/     # basic, memory, mcp_memory
│   ├── api/                     # FastAPI app (app.py)
│   ├── core/
│   ├── domain/
│   ├── infrastructure/
│   ├── interfaces/              # CLI + Gradio
│   ├── tools/
│   │   ├── registry.py
│   │   └── builtins/
│   └── mcp/servers/             # MCP server scripts
├── data/                        # local runtime (users.db gitignored)
│   ├── google/                  # OAuth credentials per user
│   └── mcp/server_config.json
├── scripts/users/               # CSV + notebook to seed data/users.db
├── examples/                    # experimental scripts + fixtures/
├── tests/
├── requirements.txt             # uv export for Hugging Face Spaces
├── app.py                       # Gradio shim for Hugging Face Spaces
└── pyproject.toml
```

## Roadmap
- [x] Basic chatbot
- [x] Zephyr, Ollama Mistral and GPT models implemented
- [x] Conversational memory. Cache management
- [x] Tools functionality
- [x] Gradio UI
- [x] Speech-to-text tool
- [x] Basic API endpoints
- [x] Prompt Engineering - Jarvis background
- [x] User ID pt 1 - DB and secret DB
- [x] User ID pt 2 - Session wrapper class
- [x] MCP - Jarvis MCP Memory Agent
- [x] Upload to Render and expose API
- [x] Google Calendar API
- [x] JWT Token Security
- [x] Raspberry Pi / Server version
- [x] Cloudflare API exposure - Firebase URL share
- [ ] Android app
- [ ] Multi-client management
- [ ] Security layer: MAC Address control
- [ ] Security layer: IP control and log
- [ ] Thread conversation management
- [ ] WhatsApp bot compatibility
- [ ] WhatsApp audio transcription and summarization
- [ ] Microphone - Audio prompting - Speech recognition
- [ ] Messenger: send messages between users.
- [ ] Tool to read PDFs or files
- [ ] RAG system. Vector DB
- [ ] Database implementation and interaction via LLM
- [ ] Fine-tuning functionality - Copy writting style
- [ ] Home devices control
- [ ] CrewAI functionality
- [ ] Prompt Engineering - Prompt injection detection
- [ ] Optimization: build LangGraph agent after identification
