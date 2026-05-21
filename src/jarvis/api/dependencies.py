"""FastAPI dependencies: HTTP security schemes and JWT verification."""

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBearer,
)

from api.security.jwt import get_jwt_secret_key
from core.config import JWT_ALGORITHM

security_basic = HTTPBasic()
security_bearer = HTTPBearer(auto_error=True)


def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
) -> dict:
    """
    FastAPI dependency that validates the Bearer JWT.

    Args:
        credentials: Authorization Bearer header.

    Returns:
        Decoded payload (sub, real_name, jarvis_name, is_female, admin, exp).

    Raises:
        HTTPException: 401 if the token expired or is invalid.
    """
    try:
        return jwt.decode(
            credentials.credentials,
            get_jwt_secret_key(),
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token no válido") from None


def require_admin(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Dependency that requires an admin user in the JWT.

    Args:
        user: Decoded payload from verify_jwt_token.

    Returns:
        Same user dict if admin.

    Raises:
        HTTPException: 403 if the user lacks admin privilege.
    """
    if not user.get("admin", False):
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para realizar esta acción.",
        )
    return user
