"""Deployment utilities: cloudflared, Firebase, and Telegram."""

import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from firebase_admin import credentials, db, initialize_app

from core.config import EXPOSE_API_WITH_CLOUDFLARED
from core.paths import FIREBASE_PRIVATE_KEY_PATH

logger = logging.getLogger(__name__)

# Load .env file before reading variables (avoids None values when importing the module).
load_dotenv()

API_PORT = int(os.getenv("API_PORT", 8000))


def _telegram_config() -> tuple[str | None, str | None]:
    """
    Read Telegram tokens from the environment.

    Returns:
        Tuple of (bot_token, chat_id).
    """
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")


def _firebase_config() -> tuple[str | None, str]:
    """
    Read Firebase Realtime Database configuration from the environment.

    Returns:
        Tuple of (database_url, node_path). node_path has a default value.
    """
    return os.getenv("FIREBASE_DB_URL"), os.getenv("FIREBASE_NODE_PATH", "jarvis/latest_url")


def expose_api_with_cloudflared() -> str | None:
    """
    Start a cloudflared tunnel to localhost:API_PORT.

    Returns:
        Public URL ``https://*.trycloudflare.com``, or None if not detected in time.
    """
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{API_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    public_url = None
    try:
        for _ in range(60):
            line = process.stdout.readline()
            if line:
                logger.debug("cloudflared: %s", line.strip())
                match = re.search(r"(https://.*?\.trycloudflare\.com)", line)
                if match:
                    public_url = match.group(1)
                    break
            time.sleep(0.5)
    except Exception as e:
        logger.error("Error al exponer con cloudflared: %s", e)
    return public_url


def save_url_to_firebase(url: str) -> None:
    """
    Publish the tunnel URL to Firebase Realtime Database.

    Args:
        url: Public tunnel URL.

    Returns:
        None. Logs an error if configuration is missing or the write fails.
    """
    firebase_url, firebase_path = _firebase_config()
    if not firebase_url:
        logger.error("No está configurada la URL de Firebase.")
        return

    payload = {
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        cred = credentials.Certificate(str(FIREBASE_PRIVATE_KEY_PATH))
        initialize_app(
            cred,
            {
                "databaseURL": firebase_url,
                "databaseAuthVariableOverride": {"uid": "jarvis-backend-server"},
            },
        )
        data_ref = db.reference(firebase_path)
        data_ref.set(payload)
        logger.info("URL guardada en Firebase.")
    except Exception as e:
        logger.error("Error al guardar en Firebase: %s", e)


def send_telegram_message(text: str) -> None:
    """
    Send a message to the Telegram chat configured in the environment.

    Args:
        text: Message body.

    Returns:
        None.
    """
    bot_token, chat_id = _telegram_config()
    if not bot_token or not chat_id:
        logger.warning("Falta configuración de Telegram.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except Exception as e:
        logger.error("Error al enviar mensaje Telegram: %s", e)


def run_with_optional_tunnel(start_server) -> None:
    """
    Optionally expose the API with cloudflared and start the server.

    Args:
        start_server: Zero-argument callable (e.g. start_uvicorn).

    Returns:
        None.
    """
    if EXPOSE_API_WITH_CLOUDFLARED:
        url = expose_api_with_cloudflared()
        if url:
            logger.info("La API estará disponible públicamente en: %s", url)
            send_telegram_message(f"🌐 Tu API ya está expuesta en: {url}")
            save_url_to_firebase(url)
        else:
            logger.error("No se pudo obtener URL pública.")
    else:
        logger.warning("Exposición de API desactivada")
    start_server()
