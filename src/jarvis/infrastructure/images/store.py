"""Save assistant images on disk and serve them from Jarvis.

Web-search images and later generated images share this store. User uploads
on ``/ask`` stay in the chat checkpoint and are not written here.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import socket
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

import requests

from jarvis.core.paths import IMAGES_DIR
from jarvis.infrastructure.web.policy import (
    USER_AGENT,
    UrlPolicyError,
    assert_allowed_scheme,
    assert_not_blocked,
)

logger = logging.getLogger(__name__)

WEB_KIND = "web"
GENERATED_KIND = "generated"
IMAGE_KINDS = frozenset({WEB_KIND, GENERATED_KIND})

MAX_IMAGE_FILE_BYTES = 8 * 1024 * 1024
MAX_STORED_FILES = 500
MAX_STORE_BYTES = 512 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 15.0

_MEDIA_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
_ALLOWED_EXTENSIONS = frozenset(_MEDIA_EXTENSIONS.values())

_lock = threading.RLock()


@dataclass(frozen=True)
class StoredImage:
    """One image file kept under ``data/images``."""

    image_id: str
    public_url: str
    path: Path
    media_type: str
    kind: str
    expires_at: datetime | None


def images_dir() -> Path:
    """Return the directory that holds stored image files and sidecars."""
    return IMAGES_DIR


def detect_image_media_type(data: bytes) -> str | None:
    """
    Return a supported media type when ``data`` starts with a known signature.

    Args:
        data: File bytes.

    Returns:
        ``image/jpeg``, ``image/png``, ``image/gif``, ``image/webp``, or None.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def public_image_url(image_id: str) -> str:
    """
    Build the URL embedded in chat markdown for a stored image.

    Args:
        image_id: Hex id of the file.

    Returns:
        ``{JARVIS_PUBLIC_BASE_URL}/images/{id}``, or ``/images/{id}`` when
        the base URL is unset.
    """
    from jarvis.core.config import PUBLIC_BASE_URL

    path = f"/images/{image_id}"
    base = (PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not base:
        return path
    return f"{base}{path}"


def store_image_bytes(
    data: bytes,
    *,
    kind: str,
    source_url: str | None = None,
    now: datetime | None = None,
) -> StoredImage | None:
    """
    Validate image bytes and write them under the image directory.

    The same bytes are stored once. A later save keeps the later expiry, and
    a "never expire" record is never shortened. Returns None when the bytes
    are not a supported image, exceed the per-file cap, or the store is full
    after expired files are removed.

    Args:
        data: Image bytes.
        kind: ``web`` or ``generated``.
        source_url: Original URL, when the bytes were downloaded.
        now: Clock override for tests.

    Returns:
        The stored record, or None when the bytes are rejected.

    Raises:
        ValueError: If ``kind`` is not ``web`` or ``generated``.
    """
    if kind not in IMAGE_KINDS:
        raise ValueError(f"Unknown image kind {kind!r}.")
    media_type = detect_image_media_type(data)
    if media_type is None or not data or len(data) > MAX_IMAGE_FILE_BYTES:
        return None
    moment = now or datetime.now(timezone.utc)
    image_id = hashlib.sha256(data).hexdigest()
    with _lock:
        purge_expired(now=moment)
        return _write_record(
            image_id,
            data,
            media_type=media_type,
            kind=kind,
            source_url=source_url,
            stored_at=moment,
        )


def persist_web_image(
    url: str,
    *,
    get_fn: Callable[..., Any] | None = None,
    resolve: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> StoredImage | None:
    """
    Download a public image and store it with the web-search TTL.

    Failures (policy, network, type, size, disk cap) return None so the
    caller can keep the original hotlink.

    Args:
        url: Absolute http(s) image URL.
        get_fn: Optional GET callable (tests). Signature like ``requests.get``.
        resolve: Optional resolver (tests). Signature like ``socket.getaddrinfo``.
        now: Clock override for tests.

    Returns:
        The stored record, or None when the image was not stored.
    """
    try:
        data, _media = download_image(url, get_fn=get_fn, resolve=resolve)
    except (UrlPolicyError, requests.RequestException, ValueError, OSError) as exc:
        logger.warning("Could not download image %s: %s", url, exc)
        return None
    stored = store_image_bytes(data, kind=WEB_KIND, source_url=url, now=now)
    if stored is None:
        logger.warning("Could not store image from %s (rejected or disk cap).", url)
    return stored


def download_image(
    url: str,
    *,
    get_fn: Callable[..., Any] | None = None,
    resolve: Callable[..., Any] | None = None,
) -> tuple[bytes, str]:
    """
    Download one public image and detect its media type.

    Args:
        url: Absolute http(s) URL.
        get_fn: Optional GET callable (tests).
        resolve: Optional resolver (tests).

    Returns:
        Image bytes and media type.

    Raises:
        UrlPolicyError: If the URL is empty, non-public, or blocked.
        requests.RequestException: On transport failures.
        ValueError: If the body is empty, too large, or not a supported image.
    """
    cleaned = assert_public_image_url(url, resolve=resolve)
    http_get = get_fn or requests.get
    response = http_get(
        cleaned,
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=True,
        stream=True,
    )
    try:
        response.raise_for_status()
        final_url = str(getattr(response, "url", cleaned) or cleaned)
        if final_url != cleaned:
            assert_public_image_url(final_url, resolve=resolve)
        data = _read_capped(response)
    finally:
        close = getattr(response, "close", None)
        if close:
            close()
    if not data:
        raise ValueError("Image file is empty.")
    if len(data) > MAX_IMAGE_FILE_BYTES:
        raise ValueError("Image exceeds max size.")
    media_type = detect_image_media_type(data)
    if media_type is None:
        raise ValueError("Downloaded file is not a supported image.")
    return data, media_type


def assert_public_image_url(
    url: str,
    *,
    resolve: Callable[..., Any] | None = None,
) -> str:
    """
    Reject empty, non-http, blocked, or non-public image URLs.

    Args:
        url: Candidate absolute URL.
        resolve: Optional resolver. Defaults to ``socket.getaddrinfo``.

    Returns:
        URL safe to fetch (userinfo stripped).

    Raises:
        UrlPolicyError: If the URL must not be downloaded.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise UrlPolicyError("URL is empty.")
    assert_allowed_scheme(cleaned)
    assert_not_blocked(cleaned)
    stripped = _without_userinfo(cleaned)
    host = urlparse(stripped).hostname
    if not host:
        raise UrlPolicyError("URL has no host.")
    if _host_is_non_public(host, resolve=resolve):
        raise UrlPolicyError(
            "Refusing to download an image from a non-public address."
        )
    return stripped


def purge_expired(*, now: datetime | None = None) -> int:
    """
    Delete stored images whose expiry is at or before ``now``.

    Records with no expiry (TTL 0) are kept.

    Args:
        now: Clock override for tests.

    Returns:
        How many images were removed.
    """
    moment = now or datetime.now(timezone.utc)
    root = images_dir()
    if not root.is_dir():
        return 0
    removed = 0
    with _lock:
        for partial in list(root.glob("*.partial")):
            partial.unlink(missing_ok=True)
        for meta_path in list(root.glob("*.json")):
            meta = _read_meta(meta_path)
            if meta is None:
                continue
            expires_at = _expires_from_meta(meta)
            if expires_at is None or expires_at > moment:
                continue
            _delete_record(meta_path, meta)
            removed += 1
        return removed


def open_stored_image(
    image_id: str,
    *,
    now: datetime | None = None,
) -> tuple[Path, str] | None:
    """
    Resolve a stored image for HTTP, deleting it when it is expired.

    Args:
        image_id: Hex id from the URL.
        now: Clock override for tests.

    Returns:
        File path and media type, or None when missing or expired.
    """
    if not _is_image_id(image_id):
        return None
    moment = now or datetime.now(timezone.utc)
    with _lock:
        meta_path = images_dir() / f"{image_id}.json"
        meta = _read_meta(meta_path)
        if meta is None:
            return None
        expires_at = _expires_from_meta(meta)
        if expires_at is not None and expires_at <= moment:
            _delete_record(meta_path, meta)
            return None
        path = _safe_image_path(image_id, str(meta.get("filename") or ""))
        media_type = str(meta.get("media_type") or "")
        if path is None or not path.is_file() or media_type not in _MEDIA_EXTENSIONS:
            return None
        return path, media_type


def _write_record(
    image_id: str,
    data: bytes,
    *,
    media_type: str,
    kind: str,
    source_url: str | None,
    stored_at: datetime,
) -> StoredImage | None:
    root = images_dir()
    root.mkdir(parents=True, exist_ok=True)
    extension = _MEDIA_EXTENSIONS[media_type]
    filename = f"{image_id}{extension}"
    image_path = root / filename
    meta_path = root / f"{image_id}.json"
    existing = _read_meta(meta_path) if meta_path.is_file() else None
    if existing is None and not _within_caps(len(data)):
        return None
    kind_out, ttl_days, expires_at = _merged_retention(
        existing,
        kind=kind,
        stored_at=stored_at,
    )
    if not image_path.is_file():
        temporary = root / f"{filename}.partial"
        temporary.write_bytes(data)
        temporary.replace(image_path)
    meta = {
        "id": image_id,
        "kind": kind_out,
        "media_type": media_type,
        "filename": filename,
        "stored_at": stored_at.isoformat(),
        "ttl_days": ttl_days,
        "expires_at": None if expires_at is None else expires_at.isoformat(),
        "source_url": source_url,
        "byte_size": len(data),
    }
    meta_tmp = root / f"{image_id}.json.partial"
    meta_tmp.write_text(json.dumps(meta), encoding="utf-8")
    meta_tmp.replace(meta_path)
    return StoredImage(
        image_id=image_id,
        public_url=public_image_url(image_id),
        path=image_path,
        media_type=media_type,
        kind=kind_out,
        expires_at=expires_at,
    )


def _merged_retention(
    existing: dict[str, Any] | None,
    *,
    kind: str,
    stored_at: datetime,
) -> tuple[str, int, datetime | None]:
    ttl_days = _ttl_days(kind)
    fresh_expiry = _expiry_for(ttl_days, stored_at)
    if existing is None:
        return kind, ttl_days, fresh_expiry
    old_expiry = _expires_from_meta(existing)
    old_kind = str(existing.get("kind") or kind)
    old_ttl = int(existing.get("ttl_days") or 0)
    if old_expiry is None or fresh_expiry is None:
        if fresh_expiry is None:
            return kind, ttl_days, None
        return old_kind, old_ttl, None
    if old_expiry >= fresh_expiry:
        return old_kind, old_ttl, old_expiry
    return kind, ttl_days, fresh_expiry


def _ttl_days(kind: str) -> int:
    from jarvis.core.config import GENERATED_IMAGE_TTL_DAYS, WEB_IMAGE_TTL_DAYS

    if kind == GENERATED_KIND:
        return GENERATED_IMAGE_TTL_DAYS
    return WEB_IMAGE_TTL_DAYS


def _expiry_for(ttl_days: int, stored_at: datetime) -> datetime | None:
    if ttl_days <= 0:
        return None
    return stored_at + timedelta(days=ttl_days)


def _within_caps(extra_bytes: int) -> bool:
    root = images_dir()
    files = [path for path in root.iterdir() if path.suffix.lower() in _ALLOWED_EXTENSIONS]
    if len(files) >= MAX_STORED_FILES:
        return False
    total = sum(path.stat().st_size for path in files)
    return total + extra_bytes <= MAX_STORE_BYTES


def _expires_from_meta(meta: dict[str, Any]) -> datetime | None:
    if "expires_at" not in meta or meta.get("expires_at") in (None, ""):
        return None
    return _parse_datetime(str(meta["expires_at"]))


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _read_meta(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Skipping unreadable image metadata %s", path.name)
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _delete_record(meta_path: Path, meta: dict[str, Any]) -> None:
    image_id = str(meta.get("id") or meta_path.stem)
    image_path = _safe_image_path(image_id, str(meta.get("filename") or ""))
    if image_path is not None:
        image_path.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)


def _safe_image_path(image_id: str, filename: str) -> Path | None:
    if not filename or filename != Path(filename).name:
        return None
    if Path(filename).stem != image_id:
        return None
    if Path(filename).suffix.lower() not in _ALLOWED_EXTENSIONS:
        return None
    return images_dir() / filename


def _is_image_id(image_id: str) -> bool:
    return len(image_id) == 64 and all(char in "0123456789abcdef" for char in image_id)


def _without_userinfo(url: str) -> str:
    parsed = urlparse(url)
    if parsed.username is None and parsed.password is None:
        return url
    host = parsed.hostname or ""
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunparse(parsed._replace(netloc=netloc))


def _host_is_non_public(host: str, *, resolve: Callable[..., Any] | None) -> bool:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return not literal.is_global
    resolver = resolve or socket.getaddrinfo
    try:
        infos = resolver(host, None)
    except socket.gaierror as exc:
        raise UrlPolicyError("Could not resolve image host.") from exc
    if not infos:
        raise UrlPolicyError("Could not resolve image host.")
    for info in infos:
        address = str(info[4][0]).split("%", 1)[0]
        if not ipaddress.ip_address(address).is_global:
            return True
    return False


def _read_capped(response: Any) -> bytes:
    iterator = getattr(response, "iter_content", None)
    if iterator is None:
        data = bytes(getattr(response, "content", b"") or b"")
        if len(data) > MAX_IMAGE_FILE_BYTES:
            raise ValueError("Image exceeds max size.")
        return data
    chunks: list[bytes] = []
    total = 0
    for chunk in iterator(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_IMAGE_FILE_BYTES:
            raise ValueError("Image exceeds max size.")
        chunks.append(chunk)
    return b"".join(chunks)
