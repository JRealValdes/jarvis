"""Shared Pi target settings for deploy helpers (``pi.local.env`` / ``JARVIS_PI_*``)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
LOCAL_ENV_FILE = DEPLOY_DIR / "pi.local.env"


def load_pi_local_env() -> None:
    """Load ``deploy/pi.local.env`` into ``os.environ`` if present (no override)."""
    if not LOCAL_ENV_FILE.is_file():
        return
    for raw in LOCAL_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_target() -> tuple[str, str, str]:
    """
    Read Pi SSH target from the environment.

    Returns:
        Tuple of (user, host, remote_repo_dir).

    Raises:
        SystemExit: If required settings are missing.
    """
    load_pi_local_env()
    user = os.environ.get("JARVIS_PI_USER", "").strip()
    host = os.environ.get("JARVIS_PI_HOST", "").strip()
    remote_dir = os.environ.get("JARVIS_PI_DIR", "").strip()
    missing = [
        name
        for name, value in (
            ("JARVIS_PI_USER", user),
            ("JARVIS_PI_HOST", host),
            ("JARVIS_PI_DIR", remote_dir),
        )
        if not value
    ]
    if missing:
        sys.exit(
            "Missing Pi target settings: "
            + ", ".join(missing)
            + f". Copy {LOCAL_ENV_FILE.name} from pi.env.example and fill them in."
        )
    return user, host, remote_dir.rstrip("/")


def use_systemd_user_unit() -> bool:
    """Return True when ``JARVIS_PI_SYSTEMD_USER`` requests a user unit."""
    return os.environ.get("JARVIS_PI_SYSTEMD_USER", "").strip() in {
        "1",
        "true",
        "True",
        "yes",
    }


def ssh_base(user: str, host: str, *, batch_mode: bool) -> list[str]:
    """
    Build an ``ssh`` command prefix for the Pi.

    Args:
        user: SSH username.
        host: Hostname or IP.
        batch_mode: If True, disable password prompts (fail if key auth missing).

    Returns:
        Command list starting with ``ssh``.
    """
    cmd = ["ssh"]
    if batch_mode:
        cmd.extend(["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"])
    cmd.append(f"{user}@{host}")
    return cmd


def systemctl_cmd(service: str, action: str) -> str:
    """
    Return a remote shell fragment for a systemd action on ``service``.

    Args:
        service: Unit name without ``.service``.
        action: ``stop``, ``start``, ``restart``, or ``is-active``.

    Returns:
        Shell command string for the remote host.
    """
    unit = f"{service}.service"
    if use_systemd_user_unit():
        return f"systemctl --user {action} {unit}"
    return f"sudo systemctl {action} {unit}"
