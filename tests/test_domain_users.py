"""User domain tests (prompts and identification)."""

from unittest.mock import patch

from jarvis.domain.users.identification import find_user_by_prompt
from jarvis.domain.users.prompts import (
    AUTOMATIC_RESPONSE_IF_ID_FAILED,
    build_background_prompt,
    get_welcome_message,
)


def test_get_welcome_message_female():
    msg = get_welcome_message({"jarvis_name": "María", "is_female": True})
    assert "María" in msg
    assert "Welcome" in msg


def test_get_welcome_message_male():
    msg = get_welcome_message({"jarvis_name": "Juan", "is_female": False})
    assert "Welcome" in msg
    assert "Juan" in msg


def test_build_background_prompt_valid_user():
    text = build_background_prompt(True, {"jarvis_name": "Sir", "is_female": False})
    assert "Sir" in text
    assert "friendly" in text.lower()
    assert "butler" in text.lower()


def test_build_background_prompt_intruder():
    text = build_background_prompt(False, None)
    assert "intruder" in text.lower()


def test_find_user_by_prompt_no_pattern():
    assert find_user_by_prompt("hello jarvis") is None


def test_find_user_by_prompt_spanish_soy():
    fake_user = {"real_name": "Test", "jarvis_name": "Sir", "is_female": 0, "admin": 0}
    with patch(
        "jarvis.domain.users.identification.get_user_by_field",
        return_value=fake_user,
    ) as mock_get:
        result = find_user_by_prompt("Hola, soy pepito")
    mock_get.assert_called_once_with("access_name", "pepito", is_sensitive=True)
    assert result == fake_user


def test_find_user_by_prompt_english_i_am():
    fake_user = {"real_name": "Test", "jarvis_name": "Sir", "is_female": 0, "admin": 0}
    with patch(
        "jarvis.domain.users.identification.get_user_by_field",
        return_value=fake_user,
    ) as mock_get:
        result = find_user_by_prompt("Hello, I am pepito")
    mock_get.assert_called_once_with("access_name", "pepito", is_sensitive=True)
    assert result == fake_user


def test_automatic_response_constant_exported():
    assert "identification" in AUTOMATIC_RESPONSE_IF_ID_FAILED.lower()
