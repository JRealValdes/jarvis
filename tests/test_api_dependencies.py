"""Tests for JWT utilities in api.security.jwt."""

import jwt

from jarvis.api.security.jwt import (
    build_token_payload,
    build_token_payload_from_user,
    create_jwt_token,
    encode_jwt,
)
from jarvis.core.config import JWT_ALGORITHM


def test_create_jwt_token_roundtrip():
    token = create_jwt_token("pytest-user")
    secret = __import__("os").environ["JWT_SECRET_KEY"]
    payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    assert payload["sub"] == "pytest-user"
    assert "exp" in payload


def test_build_token_payload_from_user_keys():
    user = {
        "access_name": "enc_name",
        "real_name": "Real User",
        "jarvis_name": "Sir",
        "is_female": 0,
        "admin": 1,
    }
    payload = build_token_payload_from_user(user)
    assert payload["sub"] == "enc_name"
    assert payload["real_name"] == "Real User"
    assert payload["jarvis_name"] == "Sir"
    assert payload["is_female"] is False
    assert payload["admin"] is True


def test_encode_jwt_matches_build_token_payload():
    payload = build_token_payload(sub="a", real_name="b", admin=True)
    token = encode_jwt(payload)
    secret = __import__("os").environ["JWT_SECRET_KEY"]
    decoded = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    assert decoded["sub"] == "a"
    assert decoded["real_name"] == "b"
    assert decoded["admin"] is True


def test_schemas_importable():
    from jarvis.api.schemas import AskInput, ThreadIdPayload, TokenResponse

    assert AskInput(message="hola").message == "hola"
    assert ThreadIdPayload().thread_id is None
    assert TokenResponse(access_token="x").token_type == "bearer"
