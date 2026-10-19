"""Tests for show/add LinkedIn reply example tools."""

import pytest

from jarvis.infrastructure.users.linkedin_reply_examples import (
    load_linkedin_reply_example_entries,
)
from jarvis.tools.builtins.linkedin_reply_examples import (
    add_linkedin_reply_example_tool,
    prepare_english_example_body,
    show_linkedin_reply_examples_tool,
)


def test_show_tool_no_real_name():
    result = show_linkedin_reply_examples_tool.invoke({"real_name": ""})
    assert "no real_name" in result.lower()


def test_show_tool_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    result = show_linkedin_reply_examples_tool.invoke({"real_name": "alice"})
    assert "No LinkedIn reply examples found" in result
    assert "add_linkedin_reply_example_tool" in result


def test_prepare_english_passthrough():
    body = "Hi Eva,\n\nThank you for reaching out.\n\nBest regards,"
    english, was_translated = prepare_english_example_body(body)
    assert english == body
    assert was_translated is False


def test_prepare_english_translates_non_english():
    body = "Hola Eva,\n\nGracias por contactarme.\n\nUn saludo,"
    english, was_translated = prepare_english_example_body(
        body,
        translate=lambda text: "Hi Eva,\n\nThank you for contacting me.\n\nRegards,",
    )
    assert was_translated is True
    assert english.startswith("Hi Eva")
    assert "Gracias" not in english


def test_prepare_english_rejects_empty_translation():
    with pytest.raises(ValueError, match="empty English body"):
        prepare_english_example_body(
            "Hola, gracias por contactarme sobre la oportunidad.",
            translate=lambda _text: "   ",
        )


def test_add_tool_refuses_without_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    body = "Hi Eva,\n\nThank you for reaching out.\n\nBest regards,"
    result = add_linkedin_reply_example_tool.invoke(
        {
            "message_body": body,
            "label": "thanks",
            "confirmed": False,
            "real_name": "alice",
        }
    )
    assert "Refused" in result
    assert body in result
    assert "Translated to English" not in result
    assert load_linkedin_reply_example_entries("alice") == []


def test_add_tool_preview_shows_translation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "jarvis.tools.builtins.linkedin_reply_examples.prepare_english_example_body",
        lambda message_body, translate=None: (
            "Hi Eva,\n\nThank you for contacting me.\n\nRegards,",
            True,
        ),
    )
    result = add_linkedin_reply_example_tool.invoke(
        {
            "message_body": "Hola Eva,\n\nGracias por contactarme.\n\nUn saludo,",
            "label": "thanks",
            "confirmed": False,
            "real_name": "alice",
        }
    )
    assert "Refused" in result
    assert "Translated to English" in result
    assert "Thank you for contacting me." in result
    assert load_linkedin_reply_example_entries("alice") == []


def test_add_tool_writes_english_when_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    body = "Hi Eva,\n\nThank you for reaching out.\n\nBest regards,"
    result = add_linkedin_reply_example_tool.invoke(
        {
            "message_body": body,
            "label": "thanks en",
            "confirmed": True,
            "real_name": "alice",
        }
    )
    assert "Added LinkedIn reply example" in result
    assert "Total examples: 1" in result
    assert "Translated to English" not in result
    entries = load_linkedin_reply_example_entries("alice")
    assert len(entries) == 1
    assert entries[0]["label"] == "thanks en"
    assert entries[0]["body"] == body


def test_add_tool_writes_translated_body_when_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    english = "Hi Eva,\n\nThank you for contacting me.\n\nRegards,"
    monkeypatch.setattr(
        "jarvis.tools.builtins.linkedin_reply_examples.prepare_english_example_body",
        lambda message_body, translate=None: (english, True),
    )
    result = add_linkedin_reply_example_tool.invoke(
        {
            "message_body": "Hola Eva,\n\nGracias por contactarme.\n\nUn saludo,",
            "label": "thanks es",
            "confirmed": True,
            "real_name": "alice",
        }
    )
    assert "Added LinkedIn reply example" in result
    assert "Translated to English" in result
    entries = load_linkedin_reply_example_entries("alice")
    assert len(entries) == 1
    assert entries[0]["body"] == english


def test_add_tool_description_requires_explicit_user_request():
    description = add_linkedin_reply_example_tool.description.lower()
    assert "explicitly asks" in description
    assert "stored in english" in description or "english" in description
    assert "translat" in description
    assert "do not regenerate" in description or "paraphrase" in description


def test_example_tools_registered():
    from jarvis.tools import local_tools

    names = {getattr(t, "name", None) for t in local_tools}
    assert "show_linkedin_reply_examples_tool" in names
    assert "add_linkedin_reply_example_tool" in names
