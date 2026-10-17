"""Tests for per-user job preferences loading."""

import yaml

from jarvis.infrastructure.users.job_preferences import (
    extract_avoid_constraints,
    format_avoid_constraints_for_prompt,
    format_preferences_for_prompt,
    job_preferences_path,
    load_job_preferences,
)


def test_job_preferences_path_normalizes_name():
    path = job_preferences_path("  Alice  ")
    assert path.name == "job_preferences.yaml"
    assert path.parent.name == "alice"


def test_load_job_preferences_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    assert load_job_preferences("nobody") is None
    assert load_job_preferences("") is None


def test_load_job_preferences_reads_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "bob"
    user_dir.mkdir()
    payload = {
        "reply_style": {"tone": "concise"},
        "job_criteria": {"work_mode": "remote"},
    }
    (user_dir / "job_preferences.yaml").write_text(
        yaml.safe_dump(payload),
        encoding="utf-8",
    )
    loaded = load_job_preferences("Bob")
    assert loaded == payload


def test_load_job_preferences_rejects_non_mapping(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "carol"
    user_dir.mkdir()
    (user_dir / "job_preferences.yaml").write_text("- just a list\n", encoding="utf-8")
    assert load_job_preferences("carol") is None


def test_format_preferences_for_prompt_unset():
    text = format_preferences_for_prompt(None)
    assert "No per-user job preferences" in text


def test_format_preferences_for_prompt_dumps_yaml():
    text = format_preferences_for_prompt({"job_criteria": {"work_mode": "remote"}})
    assert "work_mode" in text
    assert "remote" in text


def test_example_user_preferences_file_exists():
    from jarvis.core.paths import USERS_DATA_DIR

    example = USERS_DATA_DIR / "example_user" / "job_preferences.yaml"
    assert example.is_file()
    data = yaml.safe_load(example.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "job_criteria" in data or "reply_style" in data


def test_extract_avoid_constraints_from_nested_keys():
    prefs = {
        "reply_style": {"avoid": ["oversharing", "I find it interesting, especially X"]},
        "tone_and_language": {
            "avoid_phrases": (
                "avoid phrases like 'I find it interesting, especially X' "
                "or similar variations"
            )
        },
    }
    constraints = extract_avoid_constraints(prefs)
    assert "oversharing" in constraints
    assert "I find it interesting, especially X" in constraints
    assert any("similar variations" in item for item in constraints)


def test_format_avoid_constraints_marks_hard_and_any_language():
    text = format_avoid_constraints_for_prompt(
        ["I find it interesting, especially X"]
    )
    assert "HARD" in text
    assert "ANY language" in text
    assert "I find it interesting, especially X" in text
