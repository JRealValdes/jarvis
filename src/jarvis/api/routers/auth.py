"""Authentication routes: Basic login and JWT validation."""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasicCredentials

from jarvis.api.dependencies import security_basic, verify_jwt_token
from jarvis.api.schemas.auth import TokenResponse
from jarvis.api.services.auth_service import auth_service

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login_for_token(
    credentials: HTTPBasicCredentials = Depends(security_basic),
) -> TokenResponse:
    """
    Authenticate with HTTP Basic and return a bearer JWT.

    Args:
        credentials: Username and password (access_name / password).

    Returns:
        TokenResponse with access_token and token_type.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    return auth_service.login(credentials.username, credentials.password)


@router.get("/validate-token")
async def validate_token(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Verify that the Bearer JWT is valid.

    Args:
        user: JWT payload (dependency).

    Returns:
        Dict with status, message, and user (claims).
    """
    return auth_service.build_validate_token_response(user)
