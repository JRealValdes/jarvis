"""Google Calendar OAuth authentication per user and account."""

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

from jarvis.core.paths import GOOGLE_CREDENTIALS_DIR

GOOGLE_API_DIR = str(GOOGLE_CREDENTIALS_DIR)


def _load_paths(user_dir: str) -> tuple[str | None, str | None]:
    """
    Locate credential_*.json and token_*.json in an account directory.

    Args:
        user_dir: Path to the Google account directory.

    Returns:
        Tuple (credential_path, token_path); either may be None.
    """
    credential_path, token_path = None, None
    for filename in os.listdir(user_dir):
        if filename.endswith(".json") and "example" not in filename:
            fp = os.path.join(user_dir, filename)
            if "credential" in filename:
                credential_path = fp
            elif "token" in filename:
                token_path = fp
    return credential_path, token_path


def _persist(creds: Credentials, token_path: str) -> None:
    """
    Persist updated OAuth credentials to disk.

    Args:
        creds: Google credentials.
        token_path: Path to the token JSON file.

    Returns:
        None.
    """
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _ensure_creds(
    credential_path: str, token_path: str | None, allow_logging_popup: bool
) -> Credentials:
    """
    Obtain valid credentials (refresh or interactive flow).

    Args:
        credential_path: Path to OAuth client secrets.
        token_path: Path to saved token (optional).
        allow_logging_popup: If False, do not open a browser and raise if token is missing.

    Returns:
        Credentials ready for the Calendar API.

    Raises:
        RuntimeError: If there is no valid token and allow_logging_popup is False.
    """
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
            logger.warning(
                "Refresh fallido (%s). Intentando flujo interactivo...", e
            )

    if not allow_logging_popup:
        raise RuntimeError(
            "No se pudo autenticar y no se permite popup. Ejecuta el flujo interactivo una vez."
        )

    flow = InstalledAppFlow.from_client_secrets_file(credential_path, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not token_path:
        token_path = credential_path.replace("credential", "token")
    _persist(creds, token_path)
    return creds


def get_authentications_for_user(
    username: str, allow_logging_popup: bool = False
) -> dict[str, Credentials]:
    """
    Load OAuth credentials for all Google accounts of a user.

    Args:
        username: Folder name under ``api/google_api/<username>/``.
        allow_logging_popup: Allow browser OAuth flow if token is missing.

    Returns:
        Dict ``{account_name: Credentials}`` for successfully authenticated accounts only.

    Raises:
        FileNotFoundError: If the user directory does not exist.
    """
    authentications: dict[str, Credentials] = {}

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
            logger.warning("Falta credential_*.json en %s", account_dir)
            continue

        try:
            creds = _ensure_creds(credential_path, token_path, allow_logging_popup)
            authentications[account] = creds
        except Exception as e:
            logger.warning("No se pudo autenticar %s: %s", account, e)

    return authentications
