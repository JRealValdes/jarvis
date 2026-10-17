"""Tests for per-user LinkedIn reply sample loading."""

import yaml

from jarvis.infrastructure.users.linkedin_reply_examples import (
    append_linkedin_reply_example,
    format_reply_examples_for_prompt,
    linkedin_reply_examples_path,
    load_linkedin_reply_example_entries,
    load_linkedin_reply_examples,
    save_linkedin_reply_examples,
)


def test_linkedin_reply_examples_path_normalizes_name():
    path = linkedin_reply_examples_path("  Alice  ")
    assert path.name == "linkedin_reply_examples.yaml"
    assert path.parent.name == "alice"


def test_load_examples_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    assert load_linkedin_reply_examples("nobody") == []
    assert load_linkedin_reply_examples("") == []


def test_load_examples_list_of_strings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "bob"
    user_dir.mkdir()
    (user_dir / "linkedin_reply_examples.yaml").write_text(
        yaml.safe_dump(["Hello one", "Hello two"]),
        encoding="utf-8",
    )
    assert load_linkedin_reply_examples("Bob") == ["Hello one", "Hello two"]


def test_load_examples_mapping_with_body(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "carol"
    user_dir.mkdir()
    payload = {
        "examples": [
            {"label": "decline", "body": "Thanks, but I will pass."},
            {"text": "  Interested — tell me more.  "},
            {"message": ""},
            "Plain string example",
        ]
    }
    (user_dir / "linkedin_reply_examples.yaml").write_text(
        yaml.safe_dump(payload),
        encoding="utf-8",
    )
    assert load_linkedin_reply_examples("carol") == [
        "Thanks, but I will pass.",
        "Interested — tell me more.",
        "Plain string example",
    ]


def test_format_reply_examples_for_prompt_empty():
    text = format_reply_examples_for_prompt([])
    assert "No sample replies" in text


def test_format_reply_examples_for_prompt_lists():
    text = format_reply_examples_for_prompt(["First", "Second"])
    assert "### Example 1" in text
    assert "First" in text
    assert "### Example 2" in text
    assert "Second" in text


def test_example_user_samples_file_exists():
    from jarvis.core.paths import USERS_DATA_DIR

    path = USERS_DATA_DIR / "example_user" / "linkedin_reply_examples.yaml"
    assert path.is_file()
    assert len(load_linkedin_reply_examples("example_user")) >= 1


def test_append_and_save_examples(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    path = append_linkedin_reply_example(
        "alice",
        "First complete sample.",
        label="first",
    )
    assert path.is_file()
    append_linkedin_reply_example("alice", "Second complete sample.")
    entries = load_linkedin_reply_example_entries("alice")
    assert len(entries) == 2
    assert entries[0]["label"] == "first"
    assert entries[1]["body"] == "Second complete sample."

    save_linkedin_reply_examples(
        "alice",
        [{"label": "only", "body": "Replaced set."}],
    )
    assert load_linkedin_reply_examples("alice") == ["Replaced set."]


def test_append_rejects_empty_body(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.linkedin_reply_examples.USERS_DATA_DIR",
        tmp_path,
    )
    try:
        append_linkedin_reply_example("alice", "   ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "empty" in str(exc).lower()
