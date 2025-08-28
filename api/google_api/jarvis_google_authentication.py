import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
GOOGLE_API_DIR = os.path.join(PROJECT_ROOT, "api", "google_api")

def _load_paths(user_dir):
    credential_path, token_path = None, None
    for filename in os.listdir(user_dir):
        if filename.endswith(".json") and "example" not in filename:
            fp = os.path.join(user_dir, filename)
            if "credential" in filename:
                credential_path = fp
            elif "token" in filename:
                token_path = fp
    return credential_path, token_path

def _persist(creds: Credentials, token_path: str):
    # Guarda access_token/refresh_token/expiry actualizados tras refresh
    with open(token_path, "w") as f:
        f.write(creds.to_json())

def _ensure_creds(credential_path: str, token_path: str, allow_logging_popup: bool) -> Credentials:
    creds = None
    if token_path and os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _persist(creds, token_path)
            return creds
        except Exception as e:
            print(f"[Auth] Refresh fallido: {e}. Intentando flujo interactivo...")

    if not allow_logging_popup:
        raise RuntimeError("No se pudo autenticar y no se permite popup. Ejecuta el flujo interactivo una vez.")

    # Flujo interactivo (solo primera vez o si hubo revocación). Forzamos refresh token “offline”.
    flow = InstalledAppFlow.from_client_secrets_file(credential_path, SCOPES)
    # IMPORTANTE: estos dos parámetros hacen que Google emita (o reemita) el refresh token
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not token_path:
        # Por si no existe, definimos un token.json al lado del credential.json
        token_path = credential_path.replace("credential", "token")
    _persist(creds, token_path)
    return creds

def get_authentications_for_user(username, allow_logging_popup=False):
    authentications = {}

    base_user_dir = os.path.join(GOOGLE_API_DIR, username)
    if not os.path.isdir(base_user_dir):
        raise FileNotFoundError(
            f"No existe el directorio para el usuario '{username}'. Ruta comprobada: {base_user_dir}"
        )

    for account in os.listdir(base_user_dir):
        account_dir = os.path.join(base_user_dir, account)
        if not os.path.isdir(account_dir):
            continue

        credential_path, token_path = _load_paths(account_dir)
        if not credential_path:
            print(f"[Auth] Falta credential_*.json en {account_dir}")
            continue

        try:
            creds = _ensure_creds(credential_path, token_path, allow_logging_popup)
            authentications[account] = creds
        except Exception as e:
            print(f"[Auth] No se pudo autenticar {account}: {e}")

    return authentications
