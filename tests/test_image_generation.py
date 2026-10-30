"""Admin-only image generation: access, one image per turn, stored URL."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from jarvis.agents.session.orchestrator import JarvisSession
from jarvis.core.enums import ModelEnum
from jarvis.infrastructure.images.generate import (
    GENERATION_TOOL_NAME,
    ImageGenerationError,
    generate_image_bytes,
    generation_allowed,
    reset_generation_budget,
    set_generation_allowed,
    visible_tools,
)
from jarvis.infrastructure.images.store import GENERATED_KIND
from jarvis.tools.builtins.generate_image import generate_image_tool

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


class _Images:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        item = SimpleNamespace(b64_json=base64.b64encode(PNG).decode("ascii"))
        return SimpleNamespace(data=[item])


class _Client:
    def __init__(self, images: _Images) -> None:
        self.images = images


@pytest.fixture
def image_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.images.store.images_dir",
        lambda: tmp_path,
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _deny_generation_unless_a_test_opts_in():
    set_generation_allowed(False)
    reset_generation_budget()
    yield
    set_generation_allowed(False)
    reset_generation_budget()


def test_non_admin_cannot_generate_or_see_the_tool():
    tool = SimpleNamespace(name=GENERATION_TOOL_NAME)
    other = SimpleNamespace(name="web_image_search_tool")
    assert visible_tools([tool, other]) == [other]
    text = generate_image_tool.invoke({"prompt": "a red square"})
    assert "admins only" in text
    assert "http" not in text


def test_admin_stores_one_png_and_a_second_call_is_blocked(
    image_root, monkeypatch: pytest.MonkeyPatch
):
    images = _Images()
    monkeypatch.setattr(
        "jarvis.infrastructure.images.generate.openai.OpenAI",
        lambda: _Client(images),
    )
    set_generation_allowed(True)
    first = generate_image_tool.invoke({"prompt": "a red square"})
    second = generate_image_tool.invoke({"prompt": "a blue square"})
    assert images.calls[0]["model"] == "gpt-image-1-mini"
    assert images.calls[0]["quality"] == "low"
    assert images.calls[0]["size"] == "1024x1024"
    assert images.calls[0]["n"] == 1
    assert "/images/" in first
    assert "already used" in second.lower()
    assert len(images.calls) == 1
    stored = list(image_root.glob("*.png"))
    assert len(stored) == 1
    meta = list(image_root.glob("*.json"))
    assert len(meta) == 1
    assert b'"kind": "generated"' in meta[0].read_bytes() or '"kind": "generated"' in meta[0].read_text(
        encoding="utf-8"
    )


def test_generated_image_uses_the_year_ttl(image_root):
    from jarvis.infrastructure.images.generate import generate_stored_image

    stored = generate_stored_image(
        "a red square",
        client=_Client(_Images()),
        now=NOW,
    )
    assert stored is not None
    assert stored.kind == GENERATED_KIND
    assert stored.expires_at == NOW + timedelta(days=365)


def test_provider_refusal_stays_text_only(monkeypatch: pytest.MonkeyPatch):
    images = _Images()
    images.error = openai.BadRequestError(
        "rejected",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body=None,
    )
    monkeypatch.setattr(
        "jarvis.infrastructure.images.generate.openai.OpenAI",
        lambda: _Client(images),
    )
    set_generation_allowed(True)
    text = generate_image_tool.invoke({"prompt": "something disallowed"})
    assert "refused" in text.lower()
    assert "http" not in text


def test_empty_prompt_does_not_spend_the_turn(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def _store(prompt: str, **_kwargs):
        calls.append(prompt)
        return SimpleNamespace(public_url="/images/abc")

    monkeypatch.setattr(
        "jarvis.tools.builtins.generate_image.generate_stored_image",
        _store,
    )
    set_generation_allowed(True)
    text = generate_image_tool.invoke({"prompt": "  "})
    follow = generate_image_tool.invoke({"prompt": "a red square"})
    assert "description" in text.lower()
    assert calls == ["a red square"]
    assert "/images/abc" in follow


def test_generate_image_bytes_rejects_a_long_prompt():
    with pytest.raises(ValueError, match="4000"):
        generate_image_bytes("x" * 4001, client=_Client(_Images()))


def test_run_model_sets_generation_from_the_user():
    captured: dict[str, bool] = {}

    class _Agent:
        async def invoke(self, **_kwargs):
            captured["allowed"] = generation_allowed()
            return {
                "messages": [
                    HumanMessage(content="draw"),
                    AIMessage(content="done"),
                ]
            }

    session = JarvisSession(
        ModelEnum.GPT_4O_MINI,
        "gen-admin-turn",
        user_info={"admin": True, "real_name": "Ada", "jarvis_name": "Sir", "is_female": False},
    )
    session._load_or_build_agent = lambda: _Agent()  # type: ignore[method-assign]
    asyncio.run(session._run_model([]))
    assert captured["allowed"] is True

    session.user = {"admin": 0, "real_name": "Ada"}
    asyncio.run(session._run_model([]))
    assert captured["allowed"] is False


def test_unreadable_provider_payload_raises():
    client = _Client(_Images())
    client.images.generate = lambda **_kwargs: SimpleNamespace(  # type: ignore[method-assign]
        data=[SimpleNamespace(b64_json="%%%")]
    )
    with pytest.raises(ImageGenerationError, match="unreadable"):
        generate_image_bytes("a red square", client=client)
