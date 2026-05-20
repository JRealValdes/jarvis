"""API HTTP FastAPI de Jarvis: ensamblado de routers y utilidades de despliegue."""

import os
import re
import subprocess
import time
from datetime import datetime, timezone

import requests
import uvicorn
from fastapi import FastAPI
from firebase_admin import credentials, db, initialize_app

from api.routers import admin, auth, chat, webhooks
from config import EXPOSE_API_WITH_CLOUDFLARED

port = int(os.getenv("API_PORT", 8000))
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
firebase_url = os.getenv("FIREBASE_DB_URL")
firebase_path = os.getenv("FIREBASE_NODE_PATH", "jarvis/latest_url")
firebase_private_key_path = "api/firebase_project_secret_private_key.json"

app = FastAPI(
    title="Jarvis API",
    description="API backend for Jarvis",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(webhooks.router)
app.include_router(admin.router)


def expose_api_with_cloudflared() -> str | None:
    """
    Arranca un túnel cloudflared hacia localhost:API_PORT.

    Returns:
        URL pública ``https://*.trycloudflare.com`` o None si no se detecta a tiempo.
    """
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    public_url = None
    try:
        for _ in range(60):
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


def save_url_to_firebase(url: str) -> None:
    """
    Publica la URL del túnel en Firebase Realtime Database.

    Args:
        url: URL pública del túnel.

    Returns:
        None. Imprime error si falta configuración o falla la escritura.
    """
    if not firebase_url:
        print("❌ No está configurada la URL de Firebase.")
        return

    payload = {
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        cred = credentials.Certificate(firebase_private_key_path)
        initialize_app(
            cred,
            {
                "databaseURL": firebase_url,
                "databaseAuthVariableOverride": {"uid": "jarvis-backend-server"},
            },
        )
        data_ref = db.reference(firebase_path)
        data_ref.set(payload)
        print("✅ URL guardada en Firebase.")
    except Exception as e:
        print(f"❌ Error al guardar en Firebase: {e}")


def send_telegram_message(text: str) -> None:
    """
    Envía un mensaje al chat de Telegram configurado en entorno.

    Args:
        text: Contenido del mensaje.

    Returns:
        None.
    """
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


def start_uvicorn() -> None:
    """Arranca el servidor ASGI en 0.0.0.0:API_PORT (bloqueante)."""
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    if EXPOSE_API_WITH_CLOUDFLARED:
        url = expose_api_with_cloudflared()
        if url:
            print(f"✅ La API estará disponible públicamente en: {url}")
            send_telegram_message(f"🌐 Tu API ya está expuesta en: {url}")
            save_url_to_firebase(url)
        else:
            print("❌ No se pudo obtener URL pública.")
    else:
        print("⚠️ Exposición de API desactivada")
    start_uvicorn()
