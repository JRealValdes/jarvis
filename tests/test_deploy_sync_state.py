"""Tests for deploy/sync_state.py (hash classify + state IO)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = REPO_ROOT / "deploy"


def _load_sync_state():
    """Load deploy/sync_state.py without installing deploy as a package."""
    path = DEPLOY_DIR / "sync_state.py"
    spec = importlib.util.spec_from_file_location("jarvis_deploy_sync_state", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sync_state = _load_sync_state()
SyncClass = sync_state.SyncClass
classify_pair = sync_state.classify_pair


def test_classify_both_equal_idle():
    assert classify_pair("aaa", "aaa", None) == SyncClass.IDLE
    assert classify_pair("aaa", "aaa", "aaa") == SyncClass.IDLE
    assert classify_pair("bbb", "bbb", "aaa") == SyncClass.IDLE


def test_classify_no_baseline_both_differ_conflict():
    assert classify_pair("local", "remote", None) == SyncClass.CONFLICT


def test_classify_no_baseline_one_side():
    assert classify_pair("local", None, None) == SyncClass.LOCAL_ONLY
    assert classify_pair(None, "remote", None) == SyncClass.REMOTE_ONLY


def test_classify_with_baseline_matrix():
    last = "base"
    assert classify_pair("base", "base", last) == SyncClass.IDLE
    assert classify_pair("local", "base", last) == SyncClass.LOCAL_ONLY
    assert classify_pair("base", "remote", last) == SyncClass.REMOTE_ONLY
    assert classify_pair("local", "remote", last) == SyncClass.CONFLICT


def test_classify_missing_vs_baseline_is_change():
    last = "base"
    assert classify_pair(None, "base", last) == SyncClass.LOCAL_ONLY
    assert classify_pair("base", None, last) == SyncClass.REMOTE_ONLY
    assert classify_pair(None, "remote", last) == SyncClass.CONFLICT
    assert classify_pair("local", None, last) == SyncClass.CONFLICT


def test_file_sha256_and_state_roundtrip(tmp_path: Path):
    target = tmp_path / "prefs.yaml"
    target.write_text("role: engineer\n", encoding="utf-8")
    digest = sync_state.file_sha256(target)
    assert len(digest) == 64

    state_file = tmp_path / ".secrets_sync_state.json"
    sync_state.save_sync_state({"data/users/a/prefs.yaml": digest}, state_file)
    loaded = sync_state.load_sync_state(state_file)
    assert loaded["data/users/a/prefs.yaml"] == digest


def test_load_sync_state_missing_or_invalid(tmp_path: Path):
    assert sync_state.load_sync_state(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    assert sync_state.load_sync_state(bad) == {}


def test_format_mtime_and_newer_hint():
    assert sync_state.format_mtime(None) == "missing"
    assert "2020" in sync_state.format_mtime(1_577_836_800.0)  # 2020-01-01 UTC-ish
    assert sync_state.newer_side_hint(10.0, 5.0) == "local"
    assert sync_state.newer_side_hint(5.0, 10.0) == "remote"
    assert sync_state.newer_side_hint(5.0, 5.0) == "same"
    assert sync_state.newer_side_hint(None, 5.0) == "n/a"
    assert sync_state.newer_side_hint(5.0, None) == "n/a"
