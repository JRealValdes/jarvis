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
uv run python main.py
uv run python app.py
uv run python api/main_api.py
```

Convención de docstrings en código de producción: módulo + **Args** / **Returns** / **Raises** (ver [docs/REFACTOR_PLAN.md](docs/REFACTOR_PLAN.md)).

## Configuration - If using OpenAI
1. Copy `.env.example` to `.env`
2. Add your OpenAI key, HF token key and Fernet key:
```
OPENAI_API_KEY=sk-...
HF_TOKEN_INFERENCE=hf_...
FERNET_KEY=...
```
3. Define users if you want to stablish your own users database. Create a database/users/secret_users_info.csv file. You can find an example at database/users/example_users_info.csv. Use database/users/manage_users.ipynb to upload the data into a users database.
4. Introduce your Google API Credentials in api/google/api as shown in the example_user. The demo at demos\google_api_demo.ipynb can help you define your authentication tokens.
5. Copy your Firebase Project credentials to: api/firebase_project_secret_private_key.json

## Usage
```bash
python main.py
```

## Architecture

Target layout and phased refactor (without breaking `ask_jarvis` or existing API routes): [docs/REFACTOR_PLAN.md](docs/REFACTOR_PLAN.md).

## Structure
```
jarvis/
├── agents/
│   ├── factory.py
│   ├── jarvis_basic_agent.py
│   ├── jarvis_mcp_memory_agent.py
│   ├── jarvis_memory_agent.py
│   └── session.py
├── api/
│   ├── main_api.py
│   ├── dependencies.py
│   ├── schemas/
│   │   ├── auth.py
│   │   └── chat.py
│   └── google_api/
│       ├── jarvis_google_authentication.py
│       └── example_user/
│           ├── jarvis_google_authentication.py
│           └── example_account/
│               ├── credentials_example.json
│               └── token_example.json
├── data/
│   ├── users.db
│   └── docs/
│       └── attention_is_all_you_need.pdf
├── database/
│   └── users/
│       ├── example_users_info.csv
│       ├── manage_users.ipynb
│       └── users_db.py
├── demos/
│   ├── basic_mcp_test.py
│   ├── chatbot_with_tools_and_memory.py
│   ├── chatbot_with_tools.py
│   ├── generate_crypt_key.ipynb
│   ├── google_api_demo.ipynb
│   └── graphrag_demo.ipynb
├── enums/
│   └── core_enums.py
├── mcp/
│   ├── server_config.json
│   └── servers/
│       └── math_server.py
├── media/
│   └── audio/
│       └── hello_world.m4a
├── tools/
│   ├── calc.py
│   ├── date_time.py
│   ├── google_calendar.py
│   ├── speech_to_text.py
│   └── tools_registry.py
├── docs/
│   └── REFACTOR_PLAN.md
├── tests/
│   ├── conftest.py
│   ├── test_smoke_imports.py
│   └── test_api_routes.py
├── pyproject.toml
├── requirements-dev.txt
├── utils/
│   └── security.py
├── .env.example
├── .gitignore
├── app.py
├── config.py
├── main.py
├── README.md
└── requirements.txt
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
