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

"Jarvis"-style AI using Langgraph and Langchain.
Hello, sir. How can I assist you today?

## Requirements
- Python 3.10+
- OpenAI API key (optional)

## Installation
```bash
python -m venv jarvis-env  
source jarvis-env/bin/activate  # or .\jarvis-env\Scripts\activate on Windows  
pip install -r requirements.txt
```

## Configuration - If using OpenAI
1. Copy `.env.example` to `.env`
2. Add your OpenAI key, HF token key and Fernet key:
```
OPENAI_API_KEY=sk-...
HF_TOKEN_INFERENCE=hf_...
FERNET_KEY=...
```

## Usage
```bash
python main.py
```

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
│   └── main_api.py
├── data/
│   └── users.db
├── database/
│   └── users/
│       ├── manage_users.ipynb
│       └── users_db.py
├── demos/
│   ├── basic_mcp_test.py
│   ├── chatbot_with_tools_and_memory.py
│   └── chatbot_with_tools.py
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
│   └── speech_to_text.py
├── utils/
│   └── security.py.py
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
- [ ] Upload to Render and expose API
- [ ] Android app
- [ ] Thread conversation management
- [ ] WhatsApp bot compatibility
- [ ] WhatsApp audio transcription and summarization
- [ ] Optimization: build LangGraph agent after identification
- [ ] Functionality: send messages through users.
- [ ] Tool to read PDFs or files
- [ ] RAG system. Vector DB
- [ ] Extra security layer
- [ ] Database implementation and interaction via LLM
- [ ] Fine-tuning functionality - Copy writting style
- [ ] Home devices control
- [ ] CrewAI functionality
- [ ] Prompt Engineering - Prompt injection detection
- [ ] Simultaneous conversations
- [ ] API backend multi-client
- [ ] Raspberry Pi / Server version
- [ ] Spech recognition
- [ ] [Optional] Security layer: IP control

Personal notes:
1. Que un tools gather coja todas las tools de los demás scripts de tools y haga la lista local_tools
2. Google Calendar API
3. API, render
4. APK
5. Multiple session
