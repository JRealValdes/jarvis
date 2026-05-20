"""Casos de uso de autenticación (login Basic → JWT)."""

import secrets

from fastapi import HTTPException, status

from api.dependencies import build_token_payload_from_user, encode_jwt
from api.schemas.auth import TokenResponse
from database.users.users_db import get_user_by_field
from utils.security import decode_symm_crypt_key


class AuthService:
    """Autenticación de usuarios y emisión de tokens."""

    def login(self, username: str, password: str) -> TokenResponse:
        """
        Valida credenciales HTTP Basic y devuelve un JWT.

        Args:
            username: access_name del usuario.
            password: Contraseña en claro.

        Returns:
            TokenResponse con access_token firmado.

        Raises:
            HTTPException: 401 si usuario o contraseña no son válidos.
        """
        user = get_user_by_field("access_name", username, is_sensitive=True)

        if not user or not secrets.compare_digest(
            password, decode_symm_crypt_key(user["password"])
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )

        token = encode_jwt(build_token_payload_from_user(user))
        return TokenResponse(access_token=token)

    def build_validate_token_response(self, user: dict) -> dict:
        """
        Formatea la respuesta de GET /validate-token.

        Args:
            user: Payload JWT decodificado.

        Returns:
            Dict con status, message y user.
        """
        return {
            "status": "ok",
            "message": "Token is valid",
            "user": user,
        }


auth_service = AuthService()
