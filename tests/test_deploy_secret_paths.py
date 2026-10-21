"""Tests for deploy/secret_paths.py (Pi secret catalog)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = REPO_ROOT / "deploy"


def _load_secret_paths():
    """Load deploy/secret_paths.py without installing deploy as a package."""
    path = DEPLOY_DIR / "secret_paths.py"
    spec = importlib.util.spec_from_file_location("jarvis_deploy_secret_paths", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


secret_paths = _load_secret_paths()


def test_list_group_names_includes_expected():
    names = secret_paths.list_group_names()
    assert "env" in names
    assert "user-prefs" in names
    assert "google" in names


def test_resolve_skips_missing_and_examples(tmp_path: Path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=x\n", encoding="utf-8")
    example = (
        tmp_path
        / "data"
        / "users"
        / "example_user"
        / "job_preferences.yaml"
    )
    example.parent.mkdir(parents=True)
    example.write_text("role: example\n", encoding="utf-8")
    real = tmp_path / "data" / "users" / "alice" / "job_preferences.yaml"
    real.parent.mkdir(parents=True)
    real.write_text("role: engineer\n", encoding="utf-8")

    paths = secret_paths.resolve_secret_paths(tmp_path)
    rels = {secret_paths.relative_to_root(p, tmp_path).as_posix() for p in paths}
    assert ".env" in rels
    assert "data/users/alice/job_preferences.yaml" in rels
    assert "data/users/example_user/job_preferences.yaml" not in rels


def test_resolve_only_filters_groups(tmp_path: Path):
    (tmp_path / ".env").write_text("x=1\n", encoding="utf-8")
    db = tmp_path / "data" / "users.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"sqlite")

    only_env = secret_paths.resolve_secret_paths(tmp_path, only=["env"])
    assert [p.name for p in only_env] == [".env"]

    only_db = secret_paths.resolve_secret_paths(tmp_path, only=["users-db"])
    assert [p.name for p in only_db] == ["users.db"]


def test_resolve_unknown_group_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown secret group"):
        secret_paths.resolve_secret_paths(tmp_path, only=["not-a-group"])


def test_google_glob_picks_secret_json(tmp_path: Path):
    secret = (
        tmp_path
        / "data"
        / "google"
        / "alice"
        / "personal"
        / "client_secret.json"
    )
    secret.parent.mkdir(parents=True)
    secret.write_text("{}", encoding="utf-8")
    example = (
        tmp_path
        / "data"
        / "google"
        / "example_user"
        / "example_account"
        / "credentials_example.json"
    )
    example.parent.mkdir(parents=True)
    example.write_text("{}", encoding="utf-8")

    paths = secret_paths.resolve_secret_paths(tmp_path, only=["google"])
    rels = {secret_paths.relative_to_root(p, tmp_path).as_posix() for p in paths}
    assert "data/google/alice/personal/client_secret.json" in rels
    assert not any("example_user" in r for r in rels)
