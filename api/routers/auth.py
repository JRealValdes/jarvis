"""Rutas de autenticación: login Basic y validación de JWT."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasicCredentials

from api.dependencies import (
    build_token_payload_from_user,
    encode_jwt,
    security_basic,
    verify_jwt_token,
)
from api.schemas.auth import TokenResponse
from database.users.users_db import get_user_by_field
from utils.security import decode_symm_crypt_key

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponse)
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


@router.get("/validate-token")
async def validate_token(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Comprueba que el Bearer JWT es válido.

    Args:
        user: Payload JWT (dependencia).

    Returns:
        Dict con status, message y user (claims).
    """
    return {
        "status": "ok",
        "message": "Token is valid",
        "user": user,
    }
