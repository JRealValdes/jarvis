#!/usr/bin/env python3
"""Update Jarvis on the Pi over SSH: git pull, uv sync, restart systemd.

Run from the repository root on the operator PC::

    uv run python deploy/update_code.py
    uv run python deploy/update_code.py --dry-run
    uv run python deploy/update_code.py --no-restart

Uses the same ``deploy/pi.local.env`` / ``JARVIS_PI_*`` settings as
``sync_secrets.py``. Requires OpenSSH ``ssh`` on PATH and a git clone of this
repo on the Pi with ``uv`` installed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
LOCAL_ENV_FILE = DEPLOY_DIR / "pi.local.env"
DEFAULT_SERVICE = "jarvis"


def _load_pi_local_env() -> None:
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


def _require_target() -> tuple[str, str, str]:
    """
    Read Pi SSH target from the environment.

    Returns:
        Tuple of (user, host, remote_repo_dir).

    Raises:
        SystemExit: If required settings are missing.
    """
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


def _run(cmd: list[str], *, dry_run: bool) -> None:
    """Print and optionally execute a subprocess command."""
    print(f"+ {' '.join(cmd)}")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def update_code(
    *,
    restart: bool,
    dry_run: bool,
    service: str = DEFAULT_SERVICE,
) -> None:
    """
    Pull latest code on the Pi, refresh the venv, and optionally restart.

    Args:
        restart: If True, run ``systemctl --user`` or ``sudo systemctl`` restart.
        dry_run: If True, print the remote command without executing.
        service: systemd unit name without ``.service``.
    """
    _load_pi_local_env()
    user, host, remote_dir = _require_target()
    use_user_unit = os.environ.get("JARVIS_PI_SYSTEMD_USER", "").strip() in {
        "1",
        "true",
        "True",
        "yes",
    }

    steps = [
        f"cd '{remote_dir}'",
        "git pull --ff-only",
        "uv sync",
    ]
    if restart:
        if use_user_unit:
            steps.append(f"systemctl --user restart {service}.service")
        else:
            steps.append(f"sudo systemctl restart {service}.service")

    remote_script = " && ".join(steps)
    _run(["ssh", f"{user}@{host}", remote_script], dry_run=dry_run)
    print("Done.")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for remote code update."""
    parser = argparse.ArgumentParser(
        description="Update Jarvis on the Pi (git pull, uv sync, restart).",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Skip systemd restart after pull/sync.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ssh command without executing it.",
    )
    parser.add_argument(
        "--service",
        default=DEFAULT_SERVICE,
        help=f"systemd unit name without .service (default: {DEFAULT_SERVICE}).",
    )
    args = parser.parse_args(argv)

    try:
        update_code(
            restart=not args.no_restart,
            dry_run=args.dry_run,
            service=args.service,
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(f"Command failed with exit code {exc.returncode}")


if __name__ == "__main__":
    main()
