#!/usr/bin/env python3
"""Update Jarvis on the Pi over SSH: stop, pull, sync, start, health-check.

Run from the repository root on the operator PC::

    uv run python deploy/update_code.py
    uv run python deploy/update_code.py --dry-run
    uv run python deploy/update_code.py --no-restart
    uv run python deploy/update_code.py --allow-password

Uses the same ``deploy/pi.local.env`` / ``JARVIS_PI_*`` settings as
``sync_secrets.py``. Requires OpenSSH ``ssh`` on PATH, a git clone on the Pi,
``uv``, and (for passwordless runs) SSH key auth plus passwordless ``sudo``
for ``systemctl`` on the jarvis unit — see ``docs/raspberry-pi-ops.md``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from pi_env import require_target, ssh_base, systemctl_cmd

DEFAULT_SERVICE = "jarvis"
DEFAULT_HEALTH_PATH = "/docs"
DEFAULT_HEALTH_PORT = 8000


def build_remote_script(
    remote_dir: str,
    *,
    restart: bool,
    service: str,
    health_port: int,
    health_path: str,
) -> str:
    """
    Build a bash script run on the Pi via SSH.

    Stops the service first (when restarting), pulls and syncs, then starts
    again. On pull/sync failure it attempts to start the previous tree so the
    API is not left down intentionally.

    Args:
        remote_dir: Absolute path to the Jarvis clone on the Pi.
        restart: If True, stop/start systemd around the update.
        service: systemd unit name without ``.service``.
        health_port: Local port for the post-start health check.
        health_path: HTTP path that must return success (e.g. ``/docs``).

    Returns:
        Remote shell script as a single string.
    """
    stop = systemctl_cmd(service, "stop")
    start = systemctl_cmd(service, "start")
    is_active = systemctl_cmd(service, "is-active")
    health_url = f"http://127.0.0.1:{health_port}{health_path}"

    lines = [
        "set -eu",
        # Non-interactive SSH has a minimal PATH; uv lives under ~/.local/bin.
        'export PATH="$HOME/.local/bin:$PATH"',
        f"cd '{remote_dir}'",
        'echo "==> repo: $(pwd) branch=$(git rev-parse --abbrev-ref HEAD) '
        'sha=$(git rev-parse --short HEAD)"',
    ]
    if restart:
        lines.extend(
            [
                f'echo "==> stopping {service}"',
                f"{stop} || true",
            ]
        )
    lines.extend(
        [
            'echo "==> git pull --ff-only"',
            "if ! git pull --ff-only; then",
            '  echo "ERROR: git pull failed" >&2',
            f"  {start} || true" if restart else "  true",
            "  exit 1",
            "fi",
            'echo "==> uv sync"',
            "if ! uv sync; then",
            '  echo "ERROR: uv sync failed" >&2',
            f"  {start} || true" if restart else "  true",
            "  exit 1",
            "fi",
        ]
    )
    if restart:
        lines.extend(
            [
                f'echo "==> starting {service}"',
                start,
                f'echo "==> waiting for {health_url}"',
                "ok=0",
                "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do",
                "  if python3 -c \"import urllib.request; "
                f"urllib.request.urlopen('{health_url}', timeout=2)\" "
                ">/dev/null 2>&1; then ok=1; break; fi",
                "  sleep 1",
                "done",
                'if [ "$ok" != 1 ]; then',
                '  echo "ERROR: health check failed after start" >&2',
                f"  {is_active} || true",
                "  exit 1",
                "fi",
                is_active,
                'echo "==> health check OK"',
            ]
        )
    lines.append('echo "==> done"')
    return "\n".join(lines)


def update_code(
    *,
    restart: bool,
    dry_run: bool,
    batch_mode: bool,
    service: str = DEFAULT_SERVICE,
    health_port: int = DEFAULT_HEALTH_PORT,
    health_path: str = DEFAULT_HEALTH_PATH,
) -> None:
    """
    Pull latest code on the Pi, refresh the venv, and optionally restart.

    Args:
        restart: If True, stop/start systemd and health-check the API.
        dry_run: If True, print the ssh command without executing.
        batch_mode: If True, SSH refuses password prompts (key auth required).
        service: systemd unit name without ``.service``.
        health_port: Port for local health check on the Pi.
        health_path: Path for local health check on the Pi.
    """
    user, host, remote_dir = require_target()
    script = build_remote_script(
        remote_dir,
        restart=restart,
        service=service,
        health_port=health_port,
        health_path=health_path,
    )
    cmd = [*ssh_base(user, host, batch_mode=batch_mode), "bash", "-s"]
    print(f"+ ssh {user}@{host} bash -s  # remote update script")
    # Always send LF newlines: Windows CRLF breaks `set -eu` / `for` on the Pi.
    script_lf = script.replace("\r\n", "\n").replace("\r", "\n")
    if dry_run:
        print("--- remote script ---")
        print(script_lf)
        print("--- end ---")
        return
    result = subprocess.run(
        cmd,
        input=script_lf.encode("utf-8"),
        check=False,
    )
    if result.returncode != 0:
        sys.exit(
            f"Remote update failed with exit code {result.returncode}. "
            "The script tries to start jarvis again after pull/sync errors; "
            "check: ssh … 'systemctl status jarvis' and journalctl -u jarvis."
        )
    print("Done.")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for remote code update."""
    parser = argparse.ArgumentParser(
        description="Update Jarvis on the Pi (stop, pull, sync, start, health-check).",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Skip systemd stop/start and health check (pull + uv sync only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the remote script without executing it.",
    )
    parser.add_argument(
        "--allow-password",
        action="store_true",
        help="Allow interactive SSH/sudo passwords (default: BatchMode key-only).",
    )
    parser.add_argument(
        "--service",
        default=DEFAULT_SERVICE,
        help=f"systemd unit name without .service (default: {DEFAULT_SERVICE}).",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        default=DEFAULT_HEALTH_PORT,
        help=f"Local API port on the Pi for health check (default: {DEFAULT_HEALTH_PORT}).",
    )
    parser.add_argument(
        "--health-path",
        default=DEFAULT_HEALTH_PATH,
        help=f"HTTP path for health check (default: {DEFAULT_HEALTH_PATH}).",
    )
    args = parser.parse_args(argv)

    try:
        update_code(
            restart=not args.no_restart,
            dry_run=args.dry_run,
            batch_mode=not args.allow_password,
            service=args.service,
            health_port=args.health_port,
            health_path=args.health_path,
        )
    except FileNotFoundError as exc:
        sys.exit(f"Required command not found: {exc.filename}")


if __name__ == "__main__":
    main()
