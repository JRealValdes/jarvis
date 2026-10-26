"""Last-sync content hashes and conflict classification for Pi secret sync.

State file (gitignored): ``deploy/.secrets_sync_state.json`` maps repo-relative
POSIX paths to SHA-256 hex digests of the last successfully synced content.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DEPLOY_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = DEPLOY_DIR / ".secrets_sync_state.json"


class SyncClass(str, Enum):
    """How local/remote relate to each other and the last-sync baseline."""

    IDLE = "idle"
    LOCAL_ONLY = "local_only"
    REMOTE_ONLY = "remote_only"
    CONFLICT = "conflict"


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sync_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, str]:
    """Load ``rel_path → sha256`` map; empty dict if missing or invalid."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def save_sync_state(
    state: dict[str, str],
    path: Path = DEFAULT_STATE_PATH,
) -> None:
    """Write sync state as sorted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = dict(sorted(state.items()))
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def classify_pair(
    local_hash: str | None,
    remote_hash: str | None,
    last_hash: str | None,
) -> SyncClass:
    """Classify a path given local, remote, and last-synced content hashes.

    ``None`` means the file is missing on that side (or never synced).

    Rules:
    - Both present and equal → ``idle`` (baseline optional).
    - No baseline and both present but different → ``conflict``.
    - With baseline: diverge on both sides with unequal content → ``conflict``.
    - Only local changed (or remote missing) → ``local_only``.
    - Only remote changed (or local missing) → ``remote_only``.
    """
    if local_hash is None and remote_hash is None:
        return SyncClass.IDLE

    if local_hash is not None and remote_hash is not None and local_hash == remote_hash:
        return SyncClass.IDLE

    if last_hash is None:
        if local_hash is not None and remote_hash is not None:
            return SyncClass.CONFLICT
        if local_hash is not None:
            return SyncClass.LOCAL_ONLY
        return SyncClass.REMOTE_ONLY

    local_changed = local_hash != last_hash
    remote_changed = remote_hash != last_hash

    # Missing file counts as a change relative to a recorded baseline.
    if local_hash is None:
        local_changed = True
    if remote_hash is None:
        remote_changed = True

    if local_changed and remote_changed:
        if local_hash is not None and remote_hash is not None and local_hash == remote_hash:
            return SyncClass.IDLE
        return SyncClass.CONFLICT
    if local_changed:
        return SyncClass.LOCAL_ONLY
    if remote_changed:
        return SyncClass.REMOTE_ONLY
    return SyncClass.IDLE


def format_mtime(mtime: float | None) -> str:
    """Format a Unix mtime for operator display (local timezone)."""
    if mtime is None:
        return "missing"
    return (
        datetime.fromtimestamp(mtime, tz=timezone.utc)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M:%S %Z")
    )


def newer_side_hint(local_mtime: float | None, remote_mtime: float | None) -> str:
    """Return which side has the newer mtime (hint only; clocks may skew).

    Returns:
        ``local``, ``remote``, ``same``, or ``n/a`` if either side is missing.
    """
    if local_mtime is None or remote_mtime is None:
        return "n/a"
    if local_mtime > remote_mtime:
        return "local"
    if remote_mtime > local_mtime:
        return "remote"
    return "same"
