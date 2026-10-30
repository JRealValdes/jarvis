"""Local image store: TTL, caps, public downloads, and the HTTP read route."""

from __future__ import annotations

import base64
import socket
from datetime import datetime, timedelta, timezone

import pytest
import requests
from fastapi.testclient import TestClient

from jarvis.api.app import app
from jarvis.infrastructure.images.store import (
    GENERATED_KIND,
    MAX_STORED_FILES,
    WEB_KIND,
    StoredImage,
    open_stored_image,
    persist_web_image,
    purge_expired,
    store_image_bytes,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
GIF = b"GIF89a" + b"\x01\x00" * 8
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _Response:
    def __init__(self, data: bytes, url: str, status: int = 200) -> None:
        self.content = data
        self.url = url
        self.status_code = status
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def iter_content(self, chunk_size: int = 65536):
        yield self.content

    def close(self) -> None:
        self.closed = True


def _public_dns(host: str, port: int | None):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0))]


def _private_dns(host: str, port: int | None):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))]


@pytest.fixture
def image_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.images.store.images_dir",
        lambda: tmp_path,
    )
    return tmp_path


def test_web_and_generated_use_different_ttls(image_root):
    web = store_image_bytes(PNG, kind=WEB_KIND, now=NOW)
    generated = store_image_bytes(GIF, kind=GENERATED_KIND, now=NOW)
    assert isinstance(web, StoredImage)
    assert isinstance(generated, StoredImage)
    assert web.expires_at == NOW + timedelta(days=30)
    assert generated.expires_at == NOW + timedelta(days=365)
    assert web.public_url == f"/images/{web.image_id}"
    assert (image_root / f"{web.image_id}.png").is_file()
    assert (image_root / f"{generated.image_id}.gif").is_file()


def test_public_base_url_is_prefixed(image_root, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "jarvis.core.config.PUBLIC_BASE_URL",
        "http://jarvis.example:8000/",
    )
    stored = store_image_bytes(PNG, kind=WEB_KIND, now=NOW)
    assert stored is not None
    assert stored.public_url == f"http://jarvis.example:8000/images/{stored.image_id}"


def test_zero_ttl_is_kept_forever(image_root, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("jarvis.core.config.WEB_IMAGE_TTL_DAYS", 0)
    stored = store_image_bytes(PNG, kind=WEB_KIND, now=NOW)
    assert stored is not None
    assert stored.expires_at is None
    assert purge_expired(now=NOW + timedelta(days=3650)) == 0
    opened = open_stored_image(stored.image_id, now=NOW + timedelta(days=3650))
    assert opened is not None


def test_expired_web_image_is_removed(image_root):
    stored = store_image_bytes(PNG, kind=WEB_KIND, now=NOW)
    assert stored is not None
    assert purge_expired(now=stored.expires_at) == 1
    assert open_stored_image(stored.image_id, now=stored.expires_at) is None
    assert list(image_root.glob("*.png")) == []
    assert list(image_root.glob("*.json")) == []


def test_generated_expiry_is_not_shortened_by_a_web_save(image_root):
    first = store_image_bytes(PNG, kind=GENERATED_KIND, now=NOW)
    again = store_image_bytes(PNG, kind=WEB_KIND, now=NOW + timedelta(days=10))
    assert first is not None and again is not None
    assert again.image_id == first.image_id
    assert again.kind == GENERATED_KIND
    assert again.expires_at == NOW + timedelta(days=365)
    assert len(list(image_root.glob("*.png"))) == 1


def test_generated_save_extends_a_web_image(image_root):
    store_image_bytes(PNG, kind=WEB_KIND, now=NOW)
    extended = store_image_bytes(PNG, kind=GENERATED_KIND, now=NOW)
    assert extended is not None
    assert extended.kind == GENERATED_KIND
    assert extended.expires_at == NOW + timedelta(days=365)


def test_store_rejects_non_images_and_unknown_kinds(image_root):
    assert store_image_bytes(b"not an image", kind=WEB_KIND, now=NOW) is None
    with pytest.raises(ValueError, match="kind"):
        store_image_bytes(PNG, kind="avatar", now=NOW)


def test_file_count_cap_refuses_a_new_image(
    image_root, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "jarvis.infrastructure.images.store.MAX_STORED_FILES",
        1,
    )
    assert MAX_STORED_FILES >= 1
    assert store_image_bytes(PNG, kind=WEB_KIND, now=NOW) is not None
    assert store_image_bytes(GIF, kind=WEB_KIND, now=NOW) is None
    assert len(list(image_root.glob("*.png"))) == 1
    assert list(image_root.glob("*.gif")) == []


def test_byte_cap_refuses_a_new_image(image_root, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.images.store.MAX_STORE_BYTES",
        len(PNG),
    )
    assert store_image_bytes(PNG, kind=WEB_KIND, now=NOW) is not None
    assert store_image_bytes(GIF, kind=WEB_KIND, now=NOW) is None


def test_download_stores_a_public_image(image_root):
    seen: list[str] = []

    def get_fn(url: str, **_kwargs):
        seen.append(url)
        return _Response(PNG, url)

    stored = persist_web_image(
        "https://user:secret@cdn.example/starry.png",
        get_fn=get_fn,
        resolve=_public_dns,
        now=NOW,
    )
    assert stored is not None
    assert seen == ["https://cdn.example/starry.png"]
    assert stored.expires_at == NOW + timedelta(days=30)
    assert stored.path.is_file()


def test_download_rejects_non_public_targets(image_root):
    def fail_get(*_args, **_kwargs):
        raise AssertionError("must not fetch")

    assert persist_web_image("http://127.0.0.1/a.png", get_fn=fail_get) is None
    assert persist_web_image("http://10.0.0.8/a.png", get_fn=fail_get) is None
    assert persist_web_image("file:///tmp/a.png", get_fn=fail_get) is None
    assert (
        persist_web_image(
            "https://rebind.example/a.png",
            get_fn=fail_get,
            resolve=_private_dns,
        )
        is None
    )
    assert list(image_root.iterdir()) == []


def test_download_rejects_a_redirect_to_a_private_host(image_root):
    def get_fn(url: str, **_kwargs):
        return _Response(PNG, "http://127.0.0.1/secret.png")

    assert (
        persist_web_image(
            "https://cdn.example/starry.png",
            get_fn=get_fn,
            resolve=_public_dns,
        )
        is None
    )
    assert list(image_root.glob("*.png")) == []


def test_download_rejects_non_image_and_oversize_bodies(
    image_root, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "jarvis.infrastructure.images.store.MAX_IMAGE_FILE_BYTES",
        len(PNG) - 1,
    )

    def html_get(url: str, **_kwargs):
        return _Response(b"<html>nope</html>", url)

    def huge_get(url: str, **_kwargs):
        return _Response(PNG, url)

    assert (
        persist_web_image(
            "https://cdn.example/page",
            get_fn=html_get,
            resolve=_public_dns,
        )
        is None
    )
    assert (
        persist_web_image(
            "https://cdn.example/big.png",
            get_fn=huge_get,
            resolve=_public_dns,
        )
        is None
    )


def test_get_stored_image_does_not_require_auth(image_root):
    stored = store_image_bytes(PNG, kind=WEB_KIND, now=datetime.now(timezone.utc))
    assert stored is not None
    response = TestClient(app).get(f"/images/{stored.image_id}")
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"].startswith("image/png")
    assert "inline" in response.headers["content-disposition"]


def test_get_missing_or_expired_image_is_404(image_root):
    stored = store_image_bytes(PNG, kind=WEB_KIND, now=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert stored is not None
    client = TestClient(app)
    missing = client.get("/images/" + "ab" * 32)
    expired = client.get(f"/images/{stored.image_id}")
    assert missing.status_code == 404
    assert expired.status_code == 404
    assert expired.json()["detail"] == "Image not found."
