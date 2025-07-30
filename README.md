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
3. Define users if you want to stablish your own users database. Create a database/users/secret_users_info.csv file. You can find an example at database/users/example_users_info.csv. Use database/users/manage_users.ipynb to upload the data into a users database.
4. Introduce your Google API Credentials in api/google/api as shown in the example_user. The demo at demos\google_api_demo.ipynb can help you define your authentication tokens.
5. Install Cloudflared if you want to be able to expose your API
6. Copy your Firebase Project credentials to: api/firebase_project_secret_private_key.json

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
│   ├── main_api.py
│   └── google_api/
│       ├── jarvis_google_authentication.py
│       └── example_user/
│           ├── jarvis_google_authentication.py
│           └── example_account/
│               ├── credentials_example.json
│               └── token_example.json
├── data/
│   └── users.db
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
│   └── google_api_demo.ipynb
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
