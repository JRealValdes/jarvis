"""Tests for deploy/update_code.py remote script builder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = REPO_ROOT / "deploy"


def _load(name: str, filename: str):
    """Load a deploy/*.py module by path."""
    path = DEPLOY_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Ensure sibling imports (pi_env) resolve when loading update_code.
    if str(DEPLOY_DIR) not in sys.path:
        sys.path.insert(0, str(DEPLOY_DIR))
    spec.loader.exec_module(module)
    return module


update_code = _load("jarvis_deploy_update_code", "update_code.py")


def test_remote_script_stops_and_health_checks_when_restarting():
    script = update_code.build_remote_script(
        "/home/jreal/jarvis",
        restart=True,
        service="jarvis",
        health_port=8000,
        health_path="/docs",
    )
    assert "set -eu" in script
    assert "git pull --ff-only" in script
    assert "uv sync" in script
    assert "systemctl stop jarvis.service" in script
    assert "systemctl start jarvis.service" in script
    assert "http://127.0.0.1:8000/docs" in script
    assert "ERROR: git pull failed" in script
    assert "ERROR: uv sync failed" in script


def test_remote_script_skips_systemd_without_restart():
    script = update_code.build_remote_script(
        "/home/jreal/jarvis",
        restart=False,
        service="jarvis",
        health_port=8000,
        health_path="/docs",
    )
    assert "git pull --ff-only" in script
    assert "systemctl stop" not in script
    assert "systemctl start" not in script


def test_remote_script_payload_uses_lf_only():
    script = update_code.build_remote_script(
        "/home/jreal/jarvis",
        restart=True,
        service="jarvis",
        health_port=8000,
        health_path="/docs",
    )
    normalized = script.replace("\r\n", "\n").replace("\r", "\n")
    assert "\r" not in normalized
    assert normalized.split("\n")[0] == "set -eu"
