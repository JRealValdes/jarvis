# Proyecto Jarvis MVP (IA Personal con Langchain)

Este es un MVP de una IA estilo "Jarvis" usando Langgraph y Langchain.
Hello, sir. How can I assist you today?

## Requisitos
- Python 3.10+
- Clave API de OpenAI (opcional)

## Instalación
```bash
python -m venv jarvis-env
source jarvis-env/bin/activate  # o .\jarvis-env\Scripts\activate en Windows
pip install -r requirements.txt
```

## Configuración - Si se usa OpenAI (no es el caso actual)
1. Copia `.env.example` como `.env`
2. Pon tu clave de OpenAI:
```
OPENAI_API_KEY=sk-...
```

## Uso
```bash
python main.py
```

## Estructura
```
project/
├── agents/
│   └── assistant.py
├── tools/
│   └── calc.py
├── main.py
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

## Roadmap
- [ ] Soporte para LLM local con `llama-cpp` o `transformers`
- [ ] Tool para leer PDFs o archivos
- [ ] Integración con micrófono y voz
- [ ] Resumen de audios de WhatsApp
- [ ] Versión para Raspberry Pi
