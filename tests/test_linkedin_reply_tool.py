"""Tests for LinkedIn reply drafting tool helpers."""

from jarvis.tools.builtins.linkedin_reply import (
    draft_linkedin_reply_tool,
    generate_linkedin_reply_draft,
)


def test_generate_linkedin_reply_draft_uses_complete_callable():
    prefs = {
        "job_criteria": {"work_mode": "remote"},
        "tone_and_language": {
            "avoid_phrases": "avoid 'I find it interesting, especially X'"
        },
    }

    def fake_complete(messages: list) -> str:
        assert len(messages) == 2
        system = messages[0].content
        human = messages[1].content
        assert "HARD CONSTRAINTS" in system
        assert "Phrases and patterns to avoid" in human
        assert "Reply language (HARD CONSTRAINT)" in human
        assert "Required language for the Proposed reply: English" in human
        assert "I find it interesting, especially X" in human
        assert "remote" in human
        assert "Hello from a recruiter" in human
        assert "ask about stack" in human
        assert "Sample replies" in human
        assert "Thank you for considering my profile" in human
        assert "polite interest" in human
        return (
            "## Fit assessment\ninterested — remote fits.\n\n"
            "## Proposed reply\nThanks for reaching out.\n\n"
            "## Confirmation required\nPlease confirm before sending."
        )

    result = generate_linkedin_reply_draft(
        "Hello from a recruiter",
        "ask about stack",
        prefs,
        reply_examples=[
            {
                "label": "polite interest",
                "body": "Thank you for considering my profile.\n\nBest,",
            }
        ],
        complete=fake_complete,
    )
    assert "## Fit assessment" in result
    assert "## Proposed reply" in result
    assert "Confirmation required" in result


def test_generate_draft_forces_english_despite_spanish_style_sample():
    spanish_style = (
        "Hola Vinita,\n\n"
        "Gracias por contactarme. Antes de continuar, me gustaría aclarar "
        "el modelo de trabajo y el tipo de contrato.\n\n"
        "Un saludo,\nJavier"
    )
    english_thread = (
        "Hi Javier, thank you for accepting my invitation. Please find the "
        "job description attached. I’d be happy to arrange a call via Teams."
    )

    def fake_complete(messages: list) -> str:
        human = messages[1].content
        assert "Required language for the Proposed reply: English" in human
        assert "style-only" in human.lower() or "style reference" in human.lower()
        assert spanish_style in human
        assert english_thread in human
        return (
            "## Fit assessment\nmaybe\n\n"
            "## Proposed reply\nHi,\n\nThank you for reaching out.\n\n"
            "## Confirmation required\nConfirm first."
        )

    generate_linkedin_reply_draft(
        english_thread,
        "",
        None,
        reply_examples=[
            {
                "label": "clarify work mode when missing",
                "body": spanish_style,
            }
        ],
        complete=fake_complete,
    )


def test_generate_draft_detects_spanish_and_allows_override():
    spanish_thread = (
        "Hola Javier, gracias por aceptar. Te adjunto la descripción del puesto."
    )

    def expect_spanish(messages: list) -> str:
        assert (
            "Required language for the Proposed reply: Spanish"
            in messages[1].content
        )
        return "## Fit assessment\nmaybe\n\n## Proposed reply\nHola\n\n## Confirmation required\nYes"

    generate_linkedin_reply_draft(
        spanish_thread,
        "",
        None,
        complete=expect_spanish,
    )

    def expect_english_override(messages: list) -> str:
        assert (
            "Required language for the Proposed reply: English"
            in messages[1].content
        )
        return "## Fit assessment\nmaybe\n\n## Proposed reply\nHi\n\n## Confirmation required\nYes"

    generate_linkedin_reply_draft(
        spanish_thread,
        "",
        None,
        reply_language="en",
        complete=expect_english_override,
    )


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
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )

    def fake_generate(
        message_context,
        user_notes,
        preferences,
        reply_examples=None,
        reply_language=None,
        complete=None,
    ):
        assert preferences is None
        assert reply_examples == []
        assert reply_language == "English"
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
    assert "Reply language: English" in result
    assert "DRAFT ONLY" in result
    assert "## Proposed reply" in result


def test_draft_tool_loads_prefs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "alice"
    user_dir.mkdir()
    (user_dir / "job_preferences.yaml").write_text(
        "job_criteria:\n  work_mode: remote\n",
        encoding="utf-8",
    )
    (user_dir / "linkedin_reply_examples.yaml").write_text(
        "examples:\n  - |\n    Sample full reply thank you.\n",
        encoding="utf-8",
    )

    def fake_generate(
        message_context,
        user_notes,
        preferences,
        reply_examples=None,
        reply_language=None,
        complete=None,
    ):
        assert preferences is not None
        assert preferences["job_criteria"]["work_mode"] == "remote"
        assert reply_examples == [
            {"label": "", "body": "Sample full reply thank you."}
        ]
        assert reply_language == "English"
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
    assert "Loaded 1 sample reply" in result
    assert "Reply language: English" in result
    assert "DRAFT ONLY" in result


def test_draft_tool_reports_missing_examples(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )

    def fake_generate(
        message_context,
        user_notes,
        preferences,
        reply_examples=None,
        reply_language=None,
        complete=None,
    ):
        assert reply_examples == []
        assert reply_language == "English"
        return "## Fit assessment\nmaybe\n\n## Proposed reply\nHi\n\n## Confirmation required\nYes"

    monkeypatch.setattr(
        "jarvis.tools.builtins.linkedin_reply.generate_linkedin_reply_draft",
        fake_generate,
    )
    result = draft_linkedin_reply_tool.invoke(
        {
            "message_context": "Any role",
            "user_notes": "",
            "real_name": "alice",
        }
    )
    assert "No sample replies file found" in result
    assert "Reply language: English" in result


def test_tool_registered_in_local_tools():
    from jarvis.tools import local_tools

    names = {getattr(t, "name", None) for t in local_tools}
    assert "draft_linkedin_reply_tool" in names
