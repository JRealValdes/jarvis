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
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status, Body
import jwt
from datetime import datetime, timedelta, timezone
import secrets
from firebase_admin import credentials, db, initialize_app
from typing import Optional

# Local dependencies
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents.session import ask_jarvis, reset_cache_global, reset_session, get_cache_status, get_message_history
from enums.core_enums import ModelEnum
from config import DEFAULT_MODEL, EXPOSE_API_WITH_CLOUDFLARED, JWT_ALGORITHM, JWT_EXP_DELTA_SECONDS
from database.users.users_db import get_user_by_field
from utils.security import decode_symm_crypt_key

# === CONFIG ===
port = int(os.getenv("API_PORT", 8000))
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
jwt_secret_key = os.getenv("JWT_SECRET_KEY")  # TODO: Change this in production
firebase_url = os.getenv("FIREBASE_DB_URL")
firebase_path = os.getenv("FIREBASE_NODE_PATH", "jarvis/latest_url")
firebase_private_key_path = "api/firebase_project_secret_private_key.json"

# === JWT Authentication ===
security_basic = HTTPBasic()
security_bearer = HTTPBearer()

def create_jwt_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }
    return jwt.encode(payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret_key, algorithms=[JWT_ALGORITHM])
        return payload  # Contains sub, real_name, jarvis_name, is_female, admin
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# === FastAPI APP ===
app = FastAPI(
    title="Jarvis API",
    description="API backend for Jarvis",
    version="1.0.0"
)

class AskInput(BaseModel):
    message: str
    model_name: str = DEFAULT_MODEL.name
    thread_id: str | None = None

class ThreadIdPayload(BaseModel):
    thread_id: Optional[str] = None

@app.post("/token")
def login_for_token(credentials: HTTPBasicCredentials = Depends(security_basic)):
    user = get_user_by_field("access_name", credentials.username, is_sensitive=True)

    if not user or not secrets.compare_digest(credentials.password, decode_symm_crypt_key(user["password"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    payload = {
        "sub": user["access_name"],
        "real_name": user["real_name"],
        "jarvis_name": user["jarvis_name"],
        "is_female": user["is_female"],
        "admin": user["admin"],
        "exp": datetime.now(timezone.utc) + timedelta(seconds=JWT_EXP_DELTA_SECONDS)
    }

    token = jwt.encode(payload, jwt_secret_key, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/ask")
async def ask_json(input_data: AskInput, user=Depends(verify_jwt_token)):
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
    user=Depends(verify_jwt_token)
):
    responses = ask_jarvis(Body, DEFAULT_MODEL, From, user_info=user)
    return PlainTextResponse("\n".join(responses))

@app.post("/reset-session")
async def reset_session_individual(
    payload: Optional[ThreadIdPayload] = Body(default=None),
    user=Depends(verify_jwt_token),
):
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
async def reset_memory_global(user=Depends(verify_jwt_token)):
    if not user.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )

    reset_cache_global()
    print("Limpieza exitosa")
    return {"status": "ok", "message": "Global memory reset"}

@app.get("/admin/cache-status")
async def cache_status(user=Depends(verify_jwt_token)):
    if not user.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    
    return get_cache_status()

@app.get("/message-history")
async def message_history(thread_id: str = None, user=Depends(verify_jwt_token)):
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
async def validate_token(user=Depends(verify_jwt_token)):
    return {
        "status": "ok",
        "message": "Token is valid",
        "user": user
    }

# === Cloudflared Exposure ===
def expose_api_with_cloudflared():
    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
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

def save_url_to_firebase(url: str):
    if not firebase_url:
        print("❌ No está configurada la URL de Firebase.")
        return
    
    payload = {
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        cred = credentials.Certificate(firebase_private_key_path)
        initialize_app(cred, {
            'databaseURL': firebase_url,
            'databaseAuthVariableOverride': {
                'uid': 'jarvis-backend-server'
            }
        })
        data_ref = db.reference(firebase_path)
        data_ref.set(payload)
        print("✅ URL guardada en Firebase.")
    except Exception as e:
        print(f"❌ Error al guardar en Firebase: {e}")

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
    start_uvicorn()  # Blocking
