#!/usr/bin/env python3
"""Sync Jarvis secrets between the operator PC and a Raspberry Pi over SSH.

Run from the repository root on the operator PC::

    uv run python deploy/sync_secrets.py
    uv run python deploy/sync_secrets.py --only env,user-prefs
    uv run python deploy/sync_secrets.py --pull --only user-prefs
    uv run python deploy/sync_secrets.py --dry-run
    uv run python deploy/sync_secrets.py --restart
    uv run python deploy/sync_secrets.py --force-local
    uv run python deploy/sync_secrets.py --allow-password

Target host settings come from environment variables or ``deploy/pi.local.env``
(see ``deploy/pi.env.example``). Requires OpenSSH ``ssh`` / ``scp`` on PATH.

Conflict detection uses content SHA-256 and ``deploy/.secrets_sync_state.json``.
On conflict the script aborts unless ``--force-local`` or ``--force-remote``.

When adding a new secret path to the project, update ``deploy/secret_paths.py``
(see that module's docstring and ``docs/raspberry-pi-ops.md``).
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from pi_env import require_target, ssh_base, systemctl_cmd
from secret_paths import (
    fixed_rels_for_groups,
    glob_patterns_for_groups,
    group_policy,
    is_example_rel,
    list_group_names,
    relative_to_root,
    resolve_secret_paths,
    selected_groups,
)
from sync_state import (
    DEFAULT_STATE_PATH,
    SyncClass,
    classify_pair,
    file_sha256,
    format_mtime,
    load_sync_state,
    newer_side_hint,
    save_sync_state,
)

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


def _run_capture(cmd: list[str]) -> str:
    """Run a command and return stdout text."""
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


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


def _remote_file_info_map(
    user: str,
    host: str,
    remote_dir: str,
    rel_posix_paths: list[str],
    *,
    batch_mode: bool,
) -> dict[str, tuple[str, float]]:
    """Return ``rel → (sha256, mtime)`` for files that exist on the remote.

    Missing files are omitted from the result.
    """
    if not rel_posix_paths:
        return {}
    remote_py = f"""
import hashlib, pathlib, json
root = pathlib.Path({remote_dir!r})
rels = {rel_posix_paths!r}
out = {{}}
for rel in rels:
    path = root / rel
    if not path.is_file():
        continue
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    key = rel.replace("\\\\", "/")
    out[key] = {{"sha256": h.hexdigest(), "mtime": path.stat().st_mtime}}
print(json.dumps(out))
"""
    stdout = _run_capture(
        [
            *ssh_base(user, host, batch_mode=batch_mode),
            f"python3 -c {shlex.quote(remote_py)}",
        ]
    ).strip()
    if not stdout:
        return {}
    data = json.loads(stdout)
    if not isinstance(data, dict):
        return {}
    out: dict[str, tuple[str, float]] = {}
    for key, value in data.items():
        rel = str(key).replace("\\", "/")
        if isinstance(value, dict) and "sha256" in value and "mtime" in value:
            out[rel] = (str(value["sha256"]), float(value["mtime"]))
    return out


def _discover_remote_glob_rels(
    user: str,
    host: str,
    remote_dir: str,
    patterns: list[str],
    *,
    batch_mode: bool,
) -> list[str]:
    """Expand catalog globs on the remote via Python (stdlib only)."""
    if not patterns:
        return []
    patterns_repr = repr(patterns)
    skip_markers = repr(("example_user", "example_account"))
    remote_py = f"""
import pathlib
root = pathlib.Path({remote_dir!r})
patterns = {patterns_repr}
skip = {skip_markers}
found = set()
for pattern in patterns:
    for path in root.glob(pattern):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = pathlib.PurePosixPath(rel).parts
        name = path.name
        if any(m in parts for m in skip):
            continue
        if name.startswith("example_") or name.endswith("_example.json"):
            continue
        found.add(rel)
for rel in sorted(found):
    print(rel)
"""
    stdout = _run_capture(
        [
            *ssh_base(user, host, batch_mode=batch_mode),
            f"python3 -c {shlex.quote(remote_py)}",
        ]
    )
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def _collect_rel_paths(
    project_root: Path,
    groups: list[str],
    *,
    pull: bool,
    user: str,
    host: str,
    remote_dir: str,
    batch_mode: bool,
) -> list[str]:
    """Union of local catalog paths and (on pull) remote-discovered paths."""
    local_paths = resolve_secret_paths(project_root, only=groups)
    rels: set[str] = {
        relative_to_root(p, project_root).as_posix() for p in local_paths
    }
    for rel in fixed_rels_for_groups(groups):
        # Include fixed catalog entries even if missing locally (pull / hash).
        if not is_example_rel(rel):
            rels.add(rel)
    if pull:
        remote_globs = _discover_remote_glob_rels(
            user,
            host,
            remote_dir,
            glob_patterns_for_groups(groups),
            batch_mode=batch_mode,
        )
        for rel in remote_globs:
            if not is_example_rel(rel):
                rels.add(rel)
    return sorted(rels)


def _decide_action(
    classification: SyncClass,
    *,
    pull: bool,
    force_local: bool,
    force_remote: bool,
) -> str | None:
    """Return ``push``, ``pull``, ``skip``, or ``block`` for one file."""
    if classification == SyncClass.IDLE:
        return "skip"
    if classification == SyncClass.CONFLICT:
        if force_local:
            return "push"
        if force_remote:
            return "pull"
        return "block"
    if classification == SyncClass.LOCAL_ONLY:
        if pull:
            if force_remote:
                # Prefer wiping local only when forcing remote — usually skip.
                return "skip"
            return "skip"
        return "push"
    if classification == SyncClass.REMOTE_ONLY:
        if pull:
            return "pull"
        if force_local:
            return "push"
        return "block"
    return "block"


def sync_secrets(
    *,
    only: list[str] | None,
    dry_run: bool,
    batch_mode: bool,
    restart: bool,
    pull: bool = False,
    force_local: bool = False,
    force_remote: bool = False,
    service: str = DEFAULT_SERVICE,
    project_root: Path = PROJECT_ROOT,
    state_path: Path = DEFAULT_STATE_PATH,
) -> int:
    """
    Sync selected secrets with the configured Pi (push or pull).

    Args:
        only: Optional group names; default is all groups.
        dry_run: If True, print actions without running ssh/scp or writing state.
        batch_mode: If True, SSH/SCP refuse password prompts.
        restart: If True, restart the systemd unit after a successful push.
        pull: If True, copy remote → local; default is local → remote.
        force_local: On conflict / remote-only during push, prefer local.
        force_remote: On conflict during pull, prefer remote.
        service: systemd unit name without ``.service``.
        project_root: Repository root.
        state_path: Path to last-sync hash state JSON.

    Returns:
        Process exit code (0 on success, 1 if nothing to do / blocked conflicts).
    """
    if force_local and force_remote:
        print("Use only one of --force-local or --force-remote.")
        return 1

    user, host, remote_dir = require_target()
    groups = selected_groups(only)
    direction = "pull" if pull else "push"
    print(f"Direction: {direction}")
    print(
        "Groups: "
        + ", ".join(f"{g} ({group_policy(g)})" for g in groups)
    )

    rel_posix = _collect_rel_paths(
        project_root,
        groups,
        pull=pull,
        user=user,
        host=host,
        remote_dir=remote_dir,
        batch_mode=batch_mode,
    )
    if not rel_posix:
        print("No secret paths found for the selected groups.")
        return 1

    state = load_sync_state(state_path)
    remote_info = _remote_file_info_map(
        user, host, remote_dir, rel_posix, batch_mode=batch_mode
    )
    remote_hashes = {rel: info[0] for rel, info in remote_info.items()}
    remote_mtimes = {rel: info[1] for rel, info in remote_info.items()}

    plans: list[tuple[str, SyncClass, str]] = []
    blocked: list[tuple[str, SyncClass, float | None, float | None]] = []

    for rel in rel_posix:
        local_path = project_root / rel
        local_hash = file_sha256(local_path) if local_path.is_file() else None
        local_mtime = local_path.stat().st_mtime if local_path.is_file() else None
        remote_hash = remote_hashes.get(rel)
        remote_mtime = remote_mtimes.get(rel)
        last_hash = state.get(rel)
        classification = classify_pair(local_hash, remote_hash, last_hash)
        action = _decide_action(
            classification,
            pull=pull,
            force_local=force_local,
            force_remote=force_remote,
        )
        if action == "block":
            blocked.append((rel, classification, local_mtime, remote_mtime))
        elif action == "push" and local_hash is None:
            print(f"  skip  [{classification.value}] {rel} (local missing)")
        elif action == "pull" and remote_hash is None:
            print(f"  skip  [{classification.value}] {rel} (remote missing)")
        elif action in ("push", "pull"):
            plans.append((rel, classification, action))
        else:
            print(f"  skip  [{classification.value}] {rel}")

    if blocked:
        print("Blocked (conflict or would clobber the other side):")
        for rel, classification, local_mtime, remote_mtime in blocked:
            hint = newer_side_hint(local_mtime, remote_mtime)
            print(f"  ! {rel} ({classification.value})")
            print(f"      local mtime:  {format_mtime(local_mtime)}")
            print(f"      remote mtime: {format_mtime(remote_mtime)}")
            print(
                f"      newer (mtime hint): {hint} "
                "(clocks may skew; not used to auto-resolve)"
            )
        print(
            "Resolve manually, or re-run with --force-local / --force-remote "
            "(and --only for a subset). No files were transferred."
        )
        return 1

    if not plans:
        print("Nothing to transfer.")
        # Still refresh baseline for idle equal files.
        if not dry_run:
            changed_state = False
            for rel in rel_posix:
                local_path = project_root / rel
                if local_path.is_file() and rel in remote_hashes:
                    digest = file_sha256(local_path)
                    if remote_hashes.get(rel) == digest and state.get(rel) != digest:
                        state[rel] = digest
                        changed_state = True
            if changed_state:
                save_sync_state(state, state_path)
                print(f"Updated sync state: {state_path}")
        return 0

    print(f"Transferring {len(plans)} file(s) ({user}@{host}:{remote_dir})")
    push_rels = [Path(rel) for rel, _, action in plans if action == "push"]
    if push_rels:
        _ensure_remote_dirs(
            user,
            host,
            remote_dir,
            push_rels,
            dry_run=dry_run,
            batch_mode=batch_mode,
        )

    for rel, classification, action in plans:
        local_path = project_root / rel
        remote_spec = f"{user}@{host}:{remote_dir}/{rel}"
        print(f"  {action} [{classification.value}] {rel}")
        if action == "push":
            _run(
                [*_scp_base(batch_mode=batch_mode), str(local_path), remote_spec],
                dry_run=dry_run,
            )
        else:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            _run(
                [*_scp_base(batch_mode=batch_mode), remote_spec, str(local_path)],
                dry_run=dry_run,
            )
        if not dry_run and local_path.is_file():
            state[rel] = file_sha256(local_path)

    if push_rels:
        _chmod_remote_files(
            user,
            host,
            remote_dir,
            push_rels,
            dry_run=dry_run,
            batch_mode=batch_mode,
        )

    if not dry_run:
        save_sync_state(state, state_path)
        print(f"Updated sync state: {state_path}")

    if restart and not pull:
        _restart_service(
            user, host, service=service, dry_run=dry_run, batch_mode=batch_mode
        )
    elif restart and pull:
        print("Note: --restart ignored on --pull (local files only).")

    print("Done.")
    return 0


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for secret sync."""
    parser = argparse.ArgumentParser(
        description=(
            "Sync Jarvis secrets with a Raspberry Pi over SSH "
            "(push by default; use --pull to retrieve)."
        ),
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
        "--pull",
        action="store_true",
        help="Copy secrets from the Pi to this machine (default: push).",
    )
    parser.add_argument(
        "--force-local",
        action="store_true",
        help="On conflict (or remote-only during push), prefer local files.",
    )
    parser.add_argument(
        "--force-remote",
        action="store_true",
        help="On conflict during pull, prefer remote files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print ssh/scp actions without executing them.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Restart jarvis.service on the Pi after a successful push.",
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
            print(f"{name}\t{group_policy(name)}")
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
            pull=args.pull,
            force_local=args.force_local,
            force_remote=args.force_remote,
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
