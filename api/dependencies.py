"""Dependencias FastAPI: seguridad HTTP/JWT y utilidades de tokens."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBearer,
)

from config import JWT_ALGORITHM, JWT_EXP_DELTA_SECONDS

security_basic = HTTPBasic()
security_bearer = HTTPBearer(auto_error=True)


def get_jwt_secret_key() -> str:
    """
    Lee la clave de firma JWT desde entorno.

    Returns:
        Valor de ``JWT_SECRET_KEY``.

    Raises:
        RuntimeError: Si la variable no está definida.
    """
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not set")
    return secret


def build_token_payload(
    *,
    sub: str,
    real_name: str | None = None,
    jarvis_name: str | None = None,
    is_female: bool | None = None,
    admin: bool | None = None,
) -> dict:
    """
    Construye el payload JWT con expiración estándar.

    Args:
        sub: Subject (access_name o username).
        real_name: Nombre real del usuario (claims extendidos tras login).
        jarvis_name: Nombre de cortesía para Jarvis.
        is_female: Género para personalización.
        admin: Privilegios de administrador.

    Returns:
        Dict listo para ``jwt.encode`` (incluye ``exp`` UTC).
    """
    payload: dict = {
        "sub": sub,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=JWT_EXP_DELTA_SECONDS),
    }
    if real_name is not None:
        payload["real_name"] = real_name
    if jarvis_name is not None:
        payload["jarvis_name"] = jarvis_name
    if is_female is not None:
        payload["is_female"] = is_female
    if admin is not None:
        payload["admin"] = admin
    return payload


def build_token_payload_from_user(user: dict) -> dict:
    """
    Payload JWT completo a partir de una fila de ``users``.

    Args:
        user: Dict devuelto por ``get_user_by_field``.

    Returns:
        Claims con sub, real_name, jarvis_name, is_female, admin y exp.
    """
    return build_token_payload(
        sub=user["access_name"],
        real_name=user["real_name"],
        jarvis_name=user["jarvis_name"],
        is_female=bool(user["is_female"]),
        admin=bool(user["admin"]),
    )


def encode_jwt(payload: dict) -> str:
    """
    Firma un payload JWT.

    Args:
        payload: Claims (debe incluir ``exp``).

    Returns:
        Token JWT como cadena.
    """
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)


def create_jwt_token(username: str) -> str:
    """
    Genera un JWT mínimo (solo sub + exp) para usos internos.

    Args:
        username: Identificador (sub).

    Returns:
        Token JWT firmado.
    """
    return encode_jwt(build_token_payload(sub=username))


def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> dict:
    """
    Dependencia FastAPI que valida el Bearer JWT.

    Args:
        credentials: Cabecera Authorization Bearer.

    Returns:
        Payload decodificado (sub, real_name, jarvis_name, is_female, admin, exp).

    Raises:
        HTTPException: 401 si el token expiró o es inválido.
    """
    try:
        return jwt.decode(
            credentials.credentials,
            get_jwt_secret_key(),
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None


def require_admin(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Dependencia que exige usuario admin en el JWT.

    Args:
        user: Payload decodificado de verify_jwt_token.

    Returns:
        Mismo dict user si es admin.

    Raises:
        HTTPException: 403 si no tiene privilegio admin.
    """
    if not user.get("admin", False):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to perform this action.",
        )
    return user
