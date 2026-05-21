"""User domain tests (prompts and identification)."""

from unittest.mock import patch

from domain.users.identification import find_user_by_prompt
from domain.users.prompts import (
    AUTOMATIC_RESPONSE_IF_ID_FAILED,
    build_background_prompt,
    get_welcome_message,
)


def test_get_welcome_message_female():
    msg = get_welcome_message({"jarvis_name": "María", "is_female": True})
    assert "María" in msg
    assert "Bienvenida" in msg


def test_get_welcome_message_male():
    msg = get_welcome_message({"jarvis_name": "Juan", "is_female": False})
    assert "Bienvenido" in msg


def test_build_background_prompt_valid_user():
    text = build_background_prompt(True, {"jarvis_name": "Sir", "is_female": False})
    assert "Sir" in text
    assert "mayordomo amigable" in text


def test_build_background_prompt_intruder():
    text = build_background_prompt(False, None)
    assert "intruso" in text


def test_find_user_by_prompt_no_pattern():
    assert find_user_by_prompt("hola jarvis") is None


def test_find_user_by_prompt_delegates_to_repository():
    fake_user = {"real_name": "Test", "jarvis_name": "Sir", "is_female": 0, "admin": 0}
    with patch(
        "domain.users.identification.get_user_by_field",
        return_value=fake_user,
    ) as mock_get:
        result = find_user_by_prompt("Hola, soy pepito")
    mock_get.assert_called_once_with("access_name", "pepito", is_sensitive=True)
    assert result == fake_user


def test_automatic_response_constant_exported():
    assert "identificación" in AUTOMATIC_RESPONSE_IF_ID_FAILED.lower()
