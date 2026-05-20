"""API HTTP FastAPI de Jarvis: auth JWT, chat, webhooks y utilidades de despliegue."""

import os
import re
import secrets
import subprocess
import time
from datetime import datetime, timezone

import requests
import uvicorn
from fastapi import Body, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPBasicCredentials
from firebase_admin import credentials, db, initialize_app

from agents.session import (
    ask_jarvis,
    check_individual_session_cache_exists,
    get_cache_status,
    get_message_history,
    reset_cache_global,
    reset_session,
)
from api.dependencies import (
    build_token_payload_from_user,
    encode_jwt,
    security_basic,
    verify_jwt_token,
)
from api.schemas.auth import TokenResponse
from api.schemas.chat import AskInput, ThreadIdPayload
from config import DEFAULT_MODEL, EXPOSE_API_WITH_CLOUDFLARED
from database.users.users_db import get_user_by_field
from enums.core_enums import ModelEnum
from utils.security import decode_symm_crypt_key

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


@app.post("/token", response_model=TokenResponse)
def login_for_token(
    credentials: HTTPBasicCredentials = Depends(security_basic),
) -> TokenResponse:
    """
    Autentica con HTTP Basic y devuelve un JWT bearer.

    Args:
        credentials: Usuario y contraseña (access_name / password).

    Returns:
        TokenResponse con access_token y token_type.

    Raises:
        HTTPException: 401 si las credenciales no son válidas.
    """
    user = get_user_by_field("access_name", credentials.username, is_sensitive=True)

    if not user or not secrets.compare_digest(
        credentials.password, decode_symm_crypt_key(user["password"])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    token = encode_jwt(build_token_payload_from_user(user))
    return TokenResponse(access_token=token)


@app.post("/ask")
async def ask_json(
    input_data: AskInput,
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Envía un mensaje a Jarvis y devuelve la respuesta.

    Args:
        input_data: Mensaje, modelo y thread_id opcional.
        user: Payload JWT (dependencia).

    Returns:
        Dict con clave ``response`` (lista de strings).
    """
    model_enum = ModelEnum[input_data.model_name]
    thread_id = input_data.thread_id or user["real_name"]
    answer = ask_jarvis(input_data.message, model_enum, thread_id, user_info=user)
    return {"response": answer}


@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    ProfileName: str = Form(None),
    user: dict = Depends(verify_jwt_token),
) -> PlainTextResponse:
    """
    Webhook Twilio/WhatsApp: reenvía el cuerpo del mensaje a Jarvis.

    Args:
        Body: Texto del mensaje entrante.
        From: Identificador del remitente (usado como thread_id).
        user: Payload JWT.

    Returns:
        PlainTextResponse con respuestas unidas por saltos de línea.
    """
    responses = ask_jarvis(Body, DEFAULT_MODEL, From, user_info=user)
    return PlainTextResponse("\n".join(responses))


@app.post("/reset-session")
async def reset_session_individual(
    payload: ThreadIdPayload | None = Body(default=None),
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Reinicia la memoria de sesión del usuario (o de otro hilo si es admin).

    Args:
        payload: thread_id opcional.
        user: Payload JWT.

    Returns:
        Dict ``{status, message}``.

    Raises:
        HTTPException: 403 si un no-admin intenta resetear otro hilo.
    """
    thread_id = payload.thread_id if payload else None
    print(f"Realizando reset session con thread_id: {thread_id}")
    if thread_id:
        if not user.get("admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to reset memory for other users.",
            )
    else:
        thread_id = user["real_name"]
    reset_session(thread_id)
    print(f"Limpieza exitosa del thread id: {thread_id}")
    return {"status": "ok", "message": "Memory reset"}


@app.post("/admin/reset-global-memory")
async def reset_memory_global(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Vacía todas las cachés de agentes y sesiones (solo admin).

    Returns:
        Dict ``{status, message}``.

    Raises:
        HTTPException: 403 si el usuario no es admin.
    """
    if not user.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )

    reset_cache_global()
    print("Limpieza exitosa")
    return {"status": "ok", "message": "Global memory reset"}


@app.get("/admin/cache-status")
async def admin_cache_status(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Estado de cachés globales (solo admin).

    Returns:
        Dict de ``get_cache_status()``.

    Raises:
        HTTPException: 403 si no es admin.
    """
    if not user.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return get_cache_status()


@app.get("/individual-cache-status")
async def individual_cache_status(user: dict = Depends(verify_jwt_token)) -> JSONResponse:
    """
    Indica si existe sesión en caché para el real_name del JWT.

    Returns:
        JSON ``{exists: bool}``.
    """
    exists = check_individual_session_cache_exists(user["real_name"])
    return JSONResponse(content={"exists": exists})


@app.get("/message-history")
async def message_history(
    thread_id: str | None = None,
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Historial de mensajes parseado para un hilo.

    Args:
        thread_id: Hilo a consultar; por defecto real_name del JWT.
        user: Payload JWT.

    Returns:
        Dict ``{thread_id, messages}``.

    Raises:
        HTTPException: 403 si un no-admin consulta otro hilo.
    """
    if thread_id:
        if not user.get("admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to reset memory for other users.",
            )
    else:
        thread_id = user["real_name"]

    history = get_message_history(thread_id)
    return {"thread_id": thread_id, "messages": history}


@app.get("/validate-token")
async def validate_token(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Comprueba que el Bearer JWT es válido.

    Returns:
        Dict con status, message y user (claims).
    """
    return {
        "status": "ok",
        "message": "Token is valid",
        "user": user,
    }


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
