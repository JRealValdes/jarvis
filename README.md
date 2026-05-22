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

Requisito: [uv](https://docs.astral.sh/uv/) (`pip install uv` o instalador oficial).

```bash
uv sync --all-groups    # crea .venv e instala dependencias + dev (pytest)
```

Para despliegues que solo lean `requirements.txt` (p. ej. Hugging Face Spaces):

```bash
uv export --no-dev -o requirements.txt
```

Instalación clásica sin uv (alternativa):

```bash
pip install -r requirements.txt
pip install -e .
```

## Development

Desde la raíz del proyecto:

```bash
uv run pytest
uv run main.py
uv run app.py
uv run -m jarvis.api
# alternativas: uv run jarvis | uv run jarvis-api
```

Convención de docstrings en código de producción: módulo + **Args** / **Returns** / **Raises**.

## Configuration - If using OpenAI
1. Copy `.env.example` to `.env`
2. Add your OpenAI key, HF token key and Fernet key:
```
OPENAI_API_KEY=sk-...
HF_TOKEN_INFERENCE=hf_...
FERNET_KEY=...
```
3. Define users if you want to stablish your own users database. Create a database/users/secret_users_info.csv file. You can find an example at database/users/example_users_info.csv. Use database/users/manage_users.ipynb to upload the data into a users database.
4. Google Calendar: place OAuth files under `data/google/<username>/<account>/` (see `data/google/example_user/`). Run `examples/google_api_demo.ipynb` for the interactive flow.
5. Copy your Firebase credentials to `data/firebase_project_secret_private_key.json` (gitignored if the filename contains `secret`).

## Usage
```bash
uv run main.py              # CLI
uv run app.py               # Gradio (Hugging Face Spaces)
uv run -m jarvis.api        # API HTTP
```

## Architecture

Installable package `jarvis` under `src/jarvis/`: `core`, `domain`, `infrastructure`, `agents`, `api`, `interfaces`, `tools`, `mcp`. Runtime data lives in `data/` at the repo root.

## Structure
```
jarvis/                          # repository root
├── src/jarvis/                  # Python package
│   ├── agents/
│   ├── api/
│   ├── core/
│   ├── domain/
│   ├── infrastructure/
│   ├── interfaces/
│   ├── tools/
│   └── mcp/
├── data/
│   ├── users.db
│   ├── google/                  # OAuth credentials per user
│   ├── firebase_project_secret_private_key.json  # (local, often gitignored)
│   └── docs/
├── database/users/              # CSV + notebook to seed users
├── examples/                    # experimental scripts/notebooks
├── tests/
├── main.py                      # CLI entry
├── app.py                       # Gradio entry (Hugging Face)
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
