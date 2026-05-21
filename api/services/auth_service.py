"""Authentication use cases (Basic login → JWT)."""

import secrets

from fastapi import HTTPException, status

from api.dependencies import build_token_payload_from_user, encode_jwt
from api.schemas.auth import TokenResponse
from infrastructure.crypto.fernet import decode_symm_crypt_key
from infrastructure.persistence.users.repository import get_user_by_field


class AuthService:
    """User authentication and token issuance."""

    def login(self, username: str, password: str) -> TokenResponse:
        """
        Validate HTTP Basic credentials and return a JWT.

        Args:
            username: User access_name.
            password: Plain-text password.

        Returns:
            TokenResponse with signed access_token.

        Raises:
            HTTPException: 401 if username or password is invalid.
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
        Format the GET /validate-token response.

        Args:
            user: Decoded JWT payload.

        Returns:
            Dict with status, message, and user.
        """
        return {
            "status": "ok",
            "message": "Token is valid",
            "user": user,
        }


auth_service = AuthService()
