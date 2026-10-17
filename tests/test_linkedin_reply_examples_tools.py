"""Tests for show/add LinkedIn reply example tools."""

from jarvis.infrastructure.users.linkedin_reply_examples import (
    load_linkedin_reply_example_entries,
)
from jarvis.tools.builtins.linkedin_reply_examples import (
    add_linkedin_reply_example_tool,
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


def test_add_tool_refuses_without_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    result = add_linkedin_reply_example_tool.invoke(
        {
            "message_body": "Gracias por contactarme.",
            "label": "thanks",
            "confirmed": False,
            "real_name": "alice",
        }
    )
    assert "Refused" in result
    assert "Gracias por contactarme." in result
    assert load_linkedin_reply_example_entries("alice") == []


def test_add_tool_writes_when_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    result = add_linkedin_reply_example_tool.invoke(
        {
            "message_body": "Gracias por contactarme.\n\nUn saludo,",
            "label": "thanks es",
            "confirmed": True,
            "real_name": "alice",
        }
    )
    assert "Added LinkedIn reply example" in result
    assert "Total examples: 1" in result
    entries = load_linkedin_reply_example_entries("alice")
    assert len(entries) == 1
    assert entries[0]["label"] == "thanks es"
    assert "Gracias por contactarme." in entries[0]["body"]


def test_example_tools_registered():
    from jarvis.tools import local_tools

    names = {getattr(t, "name", None) for t in local_tools}
    assert "show_linkedin_reply_examples_tool" in names
    assert "add_linkedin_reply_example_tool" in names
