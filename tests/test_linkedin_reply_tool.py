"""Tests for LinkedIn reply drafting tool helpers."""

from jarvis.tools.builtins.linkedin_reply import (
    draft_linkedin_reply_tool,
    generate_linkedin_reply_draft,
)


def test_generate_linkedin_reply_draft_uses_complete_callable():
    prefs = {"job_criteria": {"work_mode": "remote"}}

    def fake_complete(messages: list) -> str:
        assert len(messages) == 2
        human = messages[1].content
        assert "remote" in human
        assert "Hello from a recruiter" in human
        assert "ask about stack" in human
        return (
            "## Fit assessment\ninterested — remote fits.\n\n"
            "## Proposed reply\nThanks for reaching out.\n\n"
            "## Confirmation required\nPlease confirm before sending."
        )

    result = generate_linkedin_reply_draft(
        "Hello from a recruiter",
        "ask about stack",
        prefs,
        complete=fake_complete,
    )
    assert "## Fit assessment" in result
    assert "## Proposed reply" in result
    assert "Confirmation required" in result


def test_draft_tool_empty_context():
    result = draft_linkedin_reply_tool.invoke(
        {"message_context": "  ", "user_notes": "", "real_name": "alice"}
    )
    assert "message_context is empty" in result


def test_draft_tool_missing_prefs_and_mocked_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )

    def fake_generate(message_context, user_notes, preferences, complete=None):
        assert preferences is None
        assert "Role at Acme" in message_context
        return (
            "## Fit assessment\nmaybe\n\n"
            "## Proposed reply\nHello.\n\n"
            "## Confirmation required\nConfirm first."
        )

    monkeypatch.setattr(
        "jarvis.tools.builtins.linkedin_reply.generate_linkedin_reply_draft",
        fake_generate,
    )
    result = draft_linkedin_reply_tool.invoke(
        {
            "message_context": "Role at Acme — onsite only",
            "user_notes": "",
            "real_name": "alice",
        }
    )
    assert "No job preferences file found" in result
    assert "DRAFT ONLY" in result
    assert "## Proposed reply" in result


def test_draft_tool_loads_prefs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "alice"
    user_dir.mkdir()
    (user_dir / "job_preferences.yaml").write_text(
        "job_criteria:\n  work_mode: remote\n",
        encoding="utf-8",
    )

    def fake_generate(message_context, user_notes, preferences, complete=None):
        assert preferences is not None
        assert preferences["job_criteria"]["work_mode"] == "remote"
        return "## Fit assessment\ninterested\n\n## Proposed reply\nHi\n\n## Confirmation required\nYes"

    monkeypatch.setattr(
        "jarvis.tools.builtins.linkedin_reply.generate_linkedin_reply_draft",
        fake_generate,
    )
    result = draft_linkedin_reply_tool.invoke(
        {
            "message_context": "Remote Python role",
            "user_notes": "sound interested",
            "real_name": "Alice",
        }
    )
    assert "Loaded preferences from" in result
    assert "DRAFT ONLY" in result


def test_tool_registered_in_local_tools():
    from jarvis.tools import local_tools

    names = {getattr(t, "name", None) for t in local_tools}
    assert "draft_linkedin_reply_tool" in names
