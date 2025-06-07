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
2. Add your OpenAI key:
```
OPENAI_API_KEY=sk-...
```

## Usage
```bash
python main.py
```

## Structure
```
jarvis/
├── agents/
│   ├── __init__.py
│   ├── assistant.py
│   └── factory.py
├── api/
│   ├── __init__.py
│   └── main_api.py
├── demos/
│   ├── __init__.py
│   ├── chatbot_with_tools_and_memory.py
│   └── chatbot_with_tools.py
├── enums/
│   ├── __init__.py
│   └── core_enums.py
├── media/
│   └── audio/
│       └── hello_world.m4a
├── tools/
│   ├── __init__.py
│   ├── calc.py
│   └── speech_to_text.py
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
- [ ] Prompt Engineering - Jarvis background
- [ ] Security layer: User ID
- [ ] WhatsApp bot compatibility
- [ ] WhatsApp audio transcription and summarization
- [ ] Tool to read PDFs or files
- [ ] RAG system
- [ ] Database implementation and interaction via LLM
- [ ] Fine-tuning functionality
- [ ] Home devices control
- [ ] Android app
- [ ] CrewAI functionality
- [ ] Raspberry Pi / Server version
- [ ] Spech recognition
- [ ] [Optional] Security layer: IP control
