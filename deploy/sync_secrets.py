#!/usr/bin/env python3
"""Push local Jarvis secrets to a Raspberry Pi over SSH (scp).

Run from the repository root on the operator PC::

    uv run python deploy/sync_secrets.py
    uv run python deploy/sync_secrets.py --only env,user-prefs
    uv run python deploy/sync_secrets.py --dry-run
    uv run python deploy/sync_secrets.py --restart
    uv run python deploy/sync_secrets.py --allow-password

Target host settings come from environment variables or ``deploy/pi.local.env``
(see ``deploy/pi.env.example``). Requires OpenSSH ``ssh`` / ``scp`` on PATH.

When adding a new secret path to the project, update ``deploy/secret_paths.py``
(see that module's docstring and ``docs/raspberry-pi-ops.md``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pi_env import require_target, ssh_base, systemctl_cmd
from secret_paths import list_group_names, relative_to_root, resolve_secret_paths

DEPLOY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DEPLOY_DIR.parent
DEFAULT_SERVICE = "jarvis"


def _run(cmd: list[str], *, dry_run: bool) -> None:
    """Print and optionally execute a subprocess command."""
    printable = " ".join(cmd)
    print(f"+ {printable}")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _scp_base(*, batch_mode: bool) -> list[str]:
    """Return an ``scp`` command prefix matching SSH batch policy."""
    cmd = ["scp"]
    if batch_mode:
        cmd.extend(["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"])
    return cmd


def _ensure_remote_dirs(
    user: str,
    host: str,
    remote_dir: str,
    rel_paths: list[Path],
    *,
    dry_run: bool,
    batch_mode: bool,
) -> None:
    """Create parent directories on the Pi for each relative file path."""
    dirs = sorted(
        {
            str(Path(remote_dir) / rel.parent).replace("\\", "/")
            for rel in rel_paths
        }
    )
    if not dirs:
        return
    quoted = " ".join(f"'{d}'" for d in dirs)
    _run(
        [*ssh_base(user, host, batch_mode=batch_mode), f"mkdir -p {quoted}"],
        dry_run=dry_run,
    )


def _chmod_remote_files(
    user: str,
    host: str,
    remote_dir: str,
    rel_paths: list[Path],
    *,
    dry_run: bool,
    batch_mode: bool,
) -> None:
    """Restrict permissions on pushed secret files (owner read/write only)."""
    if not rel_paths:
        return
    remote_files = " ".join(f"'{remote_dir}/{rel.as_posix()}'" for rel in rel_paths)
    _run(
        [
            *ssh_base(user, host, batch_mode=batch_mode),
            f"chmod 600 {remote_files}",
        ],
        dry_run=dry_run,
    )


def _restart_service(
    user: str,
    host: str,
    *,
    service: str,
    dry_run: bool,
    batch_mode: bool,
) -> None:
    """Restart the Jarvis systemd unit on the Pi."""
    _run(
        [
            *ssh_base(user, host, batch_mode=batch_mode),
            systemctl_cmd(service, "restart"),
        ],
        dry_run=dry_run,
    )


def sync_secrets(
    *,
    only: list[str] | None,
    dry_run: bool,
    batch_mode: bool,
    restart: bool,
    service: str = DEFAULT_SERVICE,
    project_root: Path = PROJECT_ROOT,
) -> int:
    """
    Copy selected local secrets to the configured Pi.

    Args:
        only: Optional group names; default is all groups with local files.
        dry_run: If True, print actions without running ssh/scp.
        batch_mode: If True, SSH/SCP refuse password prompts.
        restart: If True, restart the systemd unit after a successful copy.
        service: systemd unit name without ``.service``.
        project_root: Repository root.

    Returns:
        Process exit code (0 on success, 1 if nothing to copy).
    """
    user, host, remote_dir = require_target()
    paths = resolve_secret_paths(project_root, only=only)
    if not paths:
        print("No local secret files found for the selected groups.")
        return 1

    rel_paths = [relative_to_root(p, project_root) for p in paths]
    print(f"Syncing {len(rel_paths)} file(s) to {user}@{host}:{remote_dir}")
    for rel in rel_paths:
        print(f"  - {rel.as_posix()}")

    _ensure_remote_dirs(
        user, host, remote_dir, rel_paths, dry_run=dry_run, batch_mode=batch_mode
    )
    for local, rel in zip(paths, rel_paths, strict=True):
        remote = f"{user}@{host}:{remote_dir}/{rel.as_posix()}"
        _run([*_scp_base(batch_mode=batch_mode), str(local), remote], dry_run=dry_run)
    _chmod_remote_files(
        user, host, remote_dir, rel_paths, dry_run=dry_run, batch_mode=batch_mode
    )
    if restart:
        _restart_service(
            user, host, service=service, dry_run=dry_run, batch_mode=batch_mode
        )
    print("Done.")
    return 0


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for secret sync."""
    parser = argparse.ArgumentParser(
        description="Push local Jarvis secrets to a Raspberry Pi over SSH.",
    )
    parser.add_argument(
        "--only",
        metavar="GROUPS",
        help=(
            "Comma-separated group names to sync "
            f"(default: all). Groups: {', '.join(list_group_names())}"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print ssh/scp actions without executing them.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart jarvis.service on the Pi after a successful sync.",
    )
    parser.add_argument(
        "--allow-password",
        action="store_true",
        help="Allow interactive SSH passwords (default: BatchMode key-only).",
    )
    parser.add_argument(
        "--service",
        default=DEFAULT_SERVICE,
        help=f"systemd unit name without .service (default: {DEFAULT_SERVICE}).",
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="Print known secret groups and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_groups:
        for name in list_group_names():
            print(name)
        return

    only: list[str] | None = None
    if args.only:
        only = [part.strip() for part in args.only.split(",") if part.strip()]

    try:
        code = sync_secrets(
            only=only,
            dry_run=args.dry_run,
            batch_mode=not args.allow_password,
            restart=args.restart,
            service=args.service,
        )
    except ValueError as exc:
        sys.exit(str(exc))
    except subprocess.CalledProcessError as exc:
        sys.exit(
            f"Command failed with exit code {exc.returncode}. "
            "If SSH asked for a password, set up key auth (docs/raspberry-pi-ops.md) "
            "or pass --allow-password once."
        )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
