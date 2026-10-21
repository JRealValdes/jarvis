#!/usr/bin/env python3
"""Push local Jarvis secrets to a Raspberry Pi over SSH (scp).

Run from the repository root on the operator PC::

    uv run python deploy/sync_secrets.py
    uv run python deploy/sync_secrets.py --only env,user-prefs
    uv run python deploy/sync_secrets.py --dry-run

Target host settings come from environment variables or ``deploy/pi.local.env``
(see ``deploy/pi.env.example``). Requires OpenSSH ``ssh`` / ``scp`` on PATH.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from secret_paths import list_group_names, relative_to_root, resolve_secret_paths

DEPLOY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DEPLOY_DIR.parent
LOCAL_ENV_FILE = DEPLOY_DIR / "pi.local.env"


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
    printable = " ".join(cmd)
    print(f"+ {printable}")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _ssh_base(user: str, host: str) -> list[str]:
    """Return the base ``ssh`` command for the Pi."""
    return ["ssh", f"{user}@{host}"]


def _ensure_remote_dirs(
    user: str,
    host: str,
    remote_dir: str,
    rel_paths: list[Path],
    *,
    dry_run: bool,
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
    _run([*_ssh_base(user, host), f"mkdir -p {quoted}"], dry_run=dry_run)


def _chmod_remote_files(
    user: str,
    host: str,
    remote_dir: str,
    rel_paths: list[Path],
    *,
    dry_run: bool,
) -> None:
    """Restrict permissions on pushed secret files (owner read/write only)."""
    if not rel_paths:
        return
    remote_files = " ".join(f"'{remote_dir}/{rel.as_posix()}'" for rel in rel_paths)
    _run(
        [*_ssh_base(user, host), f"chmod 600 {remote_files}"],
        dry_run=dry_run,
    )


def sync_secrets(
    *,
    only: list[str] | None,
    dry_run: bool,
    project_root: Path = PROJECT_ROOT,
) -> int:
    """
    Copy selected local secrets to the configured Pi.

    Args:
        only: Optional group names; default is all groups with local files.
        dry_run: If True, print actions without running ssh/scp.
        project_root: Repository root.

    Returns:
        Process exit code (0 on success, 1 if nothing to copy).
    """
    _load_pi_local_env()
    user, host, remote_dir = _require_target()
    paths = resolve_secret_paths(project_root, only=only)
    if not paths:
        print("No local secret files found for the selected groups.")
        return 1

    rel_paths = [relative_to_root(p, project_root) for p in paths]
    print(f"Syncing {len(rel_paths)} file(s) to {user}@{host}:{remote_dir}")
    for rel in rel_paths:
        print(f"  - {rel.as_posix()}")

    _ensure_remote_dirs(user, host, remote_dir, rel_paths, dry_run=dry_run)
    for local, rel in zip(paths, rel_paths, strict=True):
        remote = f"{user}@{host}:{remote_dir}/{rel.as_posix()}"
        _run(["scp", str(local), remote], dry_run=dry_run)
    _chmod_remote_files(user, host, remote_dir, rel_paths, dry_run=dry_run)
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
        code = sync_secrets(only=only, dry_run=args.dry_run)
    except ValueError as exc:
        sys.exit(str(exc))
    except subprocess.CalledProcessError as exc:
        sys.exit(f"Command failed with exit code {exc.returncode}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
