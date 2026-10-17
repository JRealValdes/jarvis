"""Tests for show/save job preferences tools and merge helpers."""

import yaml

from jarvis.infrastructure.users.job_preferences import (
    deep_merge_preferences,
    load_job_preferences,
    parse_preferences_yaml,
    save_job_preferences,
)
from jarvis.tools.builtins.job_preferences import (
    save_job_preferences_tool,
    show_job_preferences_tool,
)


def test_deep_merge_preferences_nested():
    base = {
        "reply_style": {"tone": "warm", "length": "short"},
        "job_criteria": {"work_mode": "remote", "tech_likes": ["Python"]},
    }
    patch = {
        "job_criteria": {"work_mode": "hybrid", "expected_salary": "60k"},
    }
    merged = deep_merge_preferences(base, patch)
    assert merged["reply_style"]["tone"] == "warm"
    assert merged["job_criteria"]["work_mode"] == "hybrid"
    assert merged["job_criteria"]["tech_likes"] == ["Python"]
    assert merged["job_criteria"]["expected_salary"] == "60k"
    assert base["job_criteria"]["work_mode"] == "remote"


def test_parse_preferences_yaml_rejects_list():
    try:
        parse_preferences_yaml("- a\n- b\n")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "mapping" in str(exc).lower()


def test_save_job_preferences_requires_real_name():
    try:
        save_job_preferences("  ", {"job_criteria": {}})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "real_name" in str(exc).lower()


def test_save_job_preferences_merge_and_replace(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    path = save_job_preferences(
        "alice",
        {"reply_style": {"tone": "concise"}, "job_criteria": {"work_mode": "remote"}},
        merge=True,
    )
    assert path.is_file()
    save_job_preferences(
        "alice",
        {"job_criteria": {"expected_salary": "55k"}},
        merge=True,
    )
    loaded = load_job_preferences("alice")
    assert loaded is not None
    assert loaded["reply_style"]["tone"] == "concise"
    assert loaded["job_criteria"]["work_mode"] == "remote"
    assert loaded["job_criteria"]["expected_salary"] == "55k"

    save_job_preferences(
        "alice",
        {"job_criteria": {"work_mode": "onsite"}},
        merge=False,
    )
    replaced = load_job_preferences("alice")
    assert replaced == {"job_criteria": {"work_mode": "onsite"}}


def test_show_tool_no_real_name():
    result = show_job_preferences_tool.invoke({"real_name": ""})
    assert "no real_name" in result.lower()


def test_show_tool_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    result = show_job_preferences_tool.invoke({"real_name": "alice"})
    assert "No job preferences file found" in result
    assert "save_job_preferences_tool" in result


def test_show_tool_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    user_dir = tmp_path / "alice"
    user_dir.mkdir()
    (user_dir / "job_preferences.yaml").write_text(
        yaml.safe_dump({"job_criteria": {"work_mode": "remote"}}),
        encoding="utf-8",
    )
    result = show_job_preferences_tool.invoke({"real_name": "Alice"})
    assert "work_mode" in result
    assert "remote" in result


def test_save_tool_refuses_without_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    result = save_job_preferences_tool.invoke(
        {
            "preferences_yaml": "job_criteria:\n  work_mode: remote\n",
            "confirmed": False,
            "real_name": "alice",
        }
    )
    assert "Refused" in result
    assert load_job_preferences("alice") is None


def test_save_tool_writes_when_confirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    result = save_job_preferences_tool.invoke(
        {
            "preferences_yaml": (
                "reply_style:\n  tone: warm\n"
                "job_criteria:\n  work_mode: remote\n"
            ),
            "confirmed": True,
            "real_name": "alice",
        }
    )
    assert "merged and saved" in result
    loaded = load_job_preferences("alice")
    assert loaded is not None
    assert loaded["job_criteria"]["work_mode"] == "remote"


def test_save_tool_replace_all(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.users.job_preferences.USERS_DATA_DIR",
        tmp_path,
    )
    save_job_preferences_tool.invoke(
        {
            "preferences_yaml": "reply_style:\n  tone: warm\n",
            "confirmed": True,
            "real_name": "alice",
        }
    )
    result = save_job_preferences_tool.invoke(
        {
            "preferences_yaml": "job_criteria:\n  work_mode: hybrid\n",
            "confirmed": True,
            "replace_all": True,
            "real_name": "alice",
        }
    )
    assert "replaced" in result
    loaded = load_job_preferences("alice")
    assert loaded == {"job_criteria": {"work_mode": "hybrid"}}


def test_preference_tools_registered():
    from jarvis.tools import local_tools

    names = {getattr(t, "name", None) for t in local_tools}
    assert "show_job_preferences_tool" in names
    assert "save_job_preferences_tool" in names
