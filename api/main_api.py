import os
import sys
import subprocess
import re
import time
import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import uvicorn

# Local dependencies
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents.session import ask_jarvis, reset_cache
from enums.core_enums import ModelEnum
from config import DEFAULT_MODEL, EXPOSE_API_WITH_CLOUDFLARED

# === CONFIG ===
PORT = 8000
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# === FastAPI APP ===
app = FastAPI(
    title="Jarvis API",
    description="API backend for Jarvis",
    version="1.0.0"
)

class AskInput(BaseModel):
    message: str
    model_name: str = DEFAULT_MODEL.name
    thread_id: str

@app.post("/ask")
async def ask_json(input_data: AskInput):
    model_enum = ModelEnum[input_data.model_name]
    answer = ask_jarvis(input_data.message, model_enum, input_data.thread_id)
    return {"response": answer}

@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    ProfileName: str = Form(None)
):
    responses = ask_jarvis(Body, DEFAULT_MODEL, From)
    return PlainTextResponse("\n".join(responses))

@app.post("/reset")
async def reset_memory():
    reset_cache()
    return {"status": "ok", "message": "Memory reset"}

# === Cloudflared Exposure ===
def expose_api_with_cloudflared():
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    public_url = None
    try:
        for _ in range(60):  # Max 60 tries
            line = process.stdout.readline()
            if line:
                print("[cloudflared] " + line.strip())
                match = re.search(r"(https://.*?\.trycloudflare\.com)", line)
                if match:
                    public_url = match.group(1)
                    break
            time.sleep(0.5)
    except Exception as e:
        print(f"❌ Error al exponer con cloudflared: {e}")
    return public_url

# === Telegram Notifier ===
def send_telegram_message(text: str):
    if not telegram_bot_token or not telegram_chat_id:
        print("⚠️ Falta configuración de Telegram.")
        return
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    data = {"chat_id": telegram_chat_id, "text": text}
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error al enviar mensaje Telegram: {e}")

# === Start API and tunnel ===
def start_uvicorn():
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    if EXPOSE_API_WITH_CLOUDFLARED:
        url = expose_api_with_cloudflared()
        if url:
            print(f"✅ API estará disponible públicamente en: {url}")
            send_telegram_message(f"🌐 Tu API ya está expuesta en: {url}")
        else:
            print("❌ No se pudo obtener URL pública.")
        start_uvicorn()  # Blocking
    else:
        print("⚠️ Exposición de API desactivada")
        start_uvicorn()  # Blocking
