"""SQLite store for mobile push device tokens."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from jarvis.core.paths import DEVICES_DB_PATH

DB_PATH = str(DEVICES_DB_PATH)
PLATFORMS = frozenset({"android", "ios", "web"})


@dataclass(frozen=True)
class DeviceTokenRecord:
    """Registered push token for a user device."""

    token: str
    owner_real_name: str
    platform: str
    created_at: str
    updated_at: str


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_devices_db() -> None:
    """
    Create the devices database and table if needed.

    Returns:
        None.
    """
    DEVICES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_tokens (
                token TEXT PRIMARY KEY,
                owner_real_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_tokens_owner "
            "ON device_tokens(owner_real_name)"
        )
        conn.commit()


def register_device_token(
    *,
    owner_real_name: str,
    token: str,
    platform: str,
) -> DeviceTokenRecord:
    """
    Upsert a device token for a user.

    Args:
        owner_real_name: JWT ``real_name``.
        token: FCM/APNs device token.
        platform: ``android``, ``ios``, or ``web``.

    Returns:
        Stored token record.

    Raises:
        ValueError: On empty token/owner or invalid platform.
    """
    owner = (owner_real_name or "").strip()
    token_clean = (token or "").strip()
    platform_clean = (platform or "").strip().lower()
    if not owner:
        raise ValueError("owner_real_name cannot be empty.")
    if not token_clean:
        raise ValueError("token cannot be empty.")
    if platform_clean not in PLATFORMS:
        raise ValueError(
            f"platform must be one of: {', '.join(sorted(PLATFORMS))}"
        )
    init_devices_db()
    now = _utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT created_at FROM device_tokens WHERE token = ?",
            (token_clean,),
        ).fetchone()
        created = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO device_tokens (
                token, owner_real_name, platform, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                owner_real_name = excluded.owner_real_name,
                platform = excluded.platform,
                updated_at = excluded.updated_at
            """,
            (token_clean, owner, platform_clean, created, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM device_tokens WHERE token = ?", (token_clean,)
        ).fetchone()
    assert row is not None
    return DeviceTokenRecord(
        token=row["token"],
        owner_real_name=row["owner_real_name"],
        platform=row["platform"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def unregister_device_token(*, owner_real_name: str, token: str) -> bool:
    """
    Delete a device token owned by the user.

    Args:
        owner_real_name: JWT ``real_name``.
        token: Token to remove.

    Returns:
        True if a row was deleted.
    """
    init_devices_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            DELETE FROM device_tokens
            WHERE token = ? AND owner_real_name = ?
            """,
            ((token or "").strip(), owner_real_name),
        )
        conn.commit()
        return cursor.rowcount > 0


def list_tokens_for_user(owner_real_name: str) -> list[DeviceTokenRecord]:
    """
    List all device tokens for a user.

    Args:
        owner_real_name: JWT ``real_name``.

    Returns:
        Registered tokens.
    """
    init_devices_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM device_tokens
            WHERE owner_real_name = ?
            ORDER BY updated_at DESC
            """,
            (owner_real_name,),
        ).fetchall()
    return [
        DeviceTokenRecord(
            token=row["token"],
            owner_real_name=row["owner_real_name"],
            platform=row["platform"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
