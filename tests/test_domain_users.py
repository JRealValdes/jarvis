"""User domain tests (prompts and identification)."""

from unittest.mock import patch

from jarvis.infrastructure.persistence.users.identification import find_user_by_prompt
from jarvis.domain.users.prompts import (
    AUTOMATIC_RESPONSE_IF_ID_FAILED,
    MARKDOWN_REPLY_GUIDANCE,
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
    assert "draft_linkedin_reply_tool" in text
    assert "show_job_preferences_tool" in text
    assert "save_job_preferences_tool" in text
    assert "add_linkedin_reply_example_tool" in text
    assert "show_linkedin_reply_examples_tool" in text
    assert "confirm" in text.lower()
    assert "english" in text.lower()
    assert "no tools to send" in text.lower()
    assert "adjust" in text.lower()
    assert "ready to send" in text.lower()
    assert "do not call draft_linkedin_reply_tool again" in text.lower()
    assert "approved wording" in text.lower()
    assert "stored in english" in text.lower()
    assert "reply in the language of the user's latest message" in text.lower()
    assert "web_search_tool" in text
    assert "web_image_search_tool" in text
    assert "Never invent" in text
    assert "at most one image" in text
    assert "current_date_time_tool" in text
    assert MARKDOWN_REPLY_GUIDANCE in text
    assert "GFM tables" in text
    assert "fenced code blocks" in text
    assert "trivial one-line answers" in text


def test_build_background_prompt_intruder():
    text = build_background_prompt(False, None)
    assert "intruder" in text.lower()
    assert MARKDOWN_REPLY_GUIDANCE in text
    assert "web_image_search_tool" not in text


def test_find_user_by_prompt_no_pattern():
    assert find_user_by_prompt("hello jarvis") is None


def test_find_user_by_prompt_spanish_soy():
    fake_user = {"real_name": "Test", "jarvis_name": "Sir", "is_female": 0, "admin": 0}
    with patch(
        "jarvis.infrastructure.persistence.users.identification.get_user_by_field",
        return_value=fake_user,
    ) as mock_get:
        result = find_user_by_prompt("Hola, soy pepito")
    mock_get.assert_called_once_with("access_name", "pepito", is_sensitive=True)
    assert result == fake_user


def test_find_user_by_prompt_english_i_am():
    fake_user = {"real_name": "Test", "jarvis_name": "Sir", "is_female": 0, "admin": 0}
    with patch(
        "jarvis.infrastructure.persistence.users.identification.get_user_by_field",
        return_value=fake_user,
    ) as mock_get:
        result = find_user_by_prompt("Hello, I am pepito")
    mock_get.assert_called_once_with("access_name", "pepito", is_sensitive=True)
    assert result == fake_user


def test_automatic_response_constant_exported():
    assert "identification" in AUTOMATIC_RESPONSE_IF_ID_FAILED.lower()
