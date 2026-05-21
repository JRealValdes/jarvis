"""FastAPI dependencies: HTTP/JWT security and token utilities."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBearer,
)

from core.config import JWT_ALGORITHM, JWT_EXP_DELTA_SECONDS

security_basic = HTTPBasic()
security_bearer = HTTPBearer(auto_error=True)


def get_jwt_secret_key() -> str:
    """
    Read the JWT signing key from the environment.

    Returns:
        Value of ``JWT_SECRET_KEY``.

    Raises:
        RuntimeError: If the variable is not set.
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
    Build a JWT payload with standard expiration.

    Args:
        sub: Subject (access_name or username).
        real_name: User's real name (extended claim after login).
        jarvis_name: Courtesy name Jarvis uses for the user.
        is_female: Gender for personalization.
        admin: Administrator privileges.

    Returns:
        Dict ready for ``jwt.encode`` (includes UTC ``exp``).
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
    Build a full JWT payload from a ``users`` row.

    Args:
        user: Dict returned by ``get_user_by_field``.

    Returns:
        Claims with sub, real_name, jarvis_name, is_female, admin, and exp.
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
    Sign a JWT payload.

    Args:
        payload: Claims (must include ``exp``).

    Returns:
        JWT token string.
    """
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)


def create_jwt_token(username: str) -> str:
    """
    Generate a minimal JWT (sub + exp only) for internal use.

    Args:
        username: Identifier (sub).

    Returns:
        Signed JWT token.
    """
    return encode_jwt(build_token_payload(sub=username))


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
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None


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
            detail="You do not have permission to perform this action.",
        )
    return user
