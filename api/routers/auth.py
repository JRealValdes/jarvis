"""Rutas de autenticación: login Basic y validación de JWT."""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasicCredentials

from api.dependencies import security_basic, verify_jwt_token
from api.schemas.auth import TokenResponse
from api.services.auth_service import auth_service

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
    return auth_service.login(credentials.username, credentials.password)


@router.get("/validate-token")
async def validate_token(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Comprueba que el Bearer JWT es válido.

    Args:
        user: Payload JWT (dependencia).

    Returns:
        Dict con status, message y user (claims).
    """
    return auth_service.build_validate_token_response(user)
