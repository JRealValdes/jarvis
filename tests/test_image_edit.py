"""Admin-only image editing: attachments, shared budget, stored URL."""

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
from jarvis.infrastructure.images.edit import (
    EditReferenceImage,
    clear_edit_reference_images,
    edit_image_bytes,
    edit_reference_images,
    edit_stored_image,
    set_edit_reference_images,
)
from jarvis.infrastructure.images.generate import (
    EDIT_TOOL_NAME,
    GENERATION_TOOL_NAME,
    ImageGenerationError,
    generation_allowed,
    reset_generation_budget,
    set_generation_allowed,
    visible_tools,
)
from jarvis.infrastructure.images.store import GENERATED_KIND
from jarvis.tools.builtins.edit_image import edit_image_tool
from jarvis.tools.builtins.generate_image import generate_image_tool

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_B64 = base64.b64encode(PNG).decode("ascii")
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


class _Images:
    def __init__(self) -> None:
        self.edit_calls: list[dict] = []
        self.generate_calls: list[dict] = []
        self.error: Exception | None = None

    def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        item = SimpleNamespace(b64_json=base64.b64encode(PNG).decode("ascii"))
        return SimpleNamespace(data=[item])

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        item = SimpleNamespace(b64_json=base64.b64encode(PNG).decode("ascii"))
        return SimpleNamespace(data=[item])


class _Client:
    def __init__(self, images: _Images) -> None:
        self.images = images


def _attachment(data_b64: str = PNG_B64) -> dict[str, str]:
    return {"media_type": "image/png", "data_base64": data_b64}


@pytest.fixture
def image_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "jarvis.infrastructure.images.store.images_dir",
        lambda: tmp_path,
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_image_turn_gates():
    set_generation_allowed(False)
    reset_generation_budget()
    clear_edit_reference_images()
    yield
    set_generation_allowed(False)
    reset_generation_budget()
    clear_edit_reference_images()


def test_non_admin_cannot_edit_or_see_the_tool():
    tool = SimpleNamespace(name=EDIT_TOOL_NAME)
    other = SimpleNamespace(name="web_image_search_tool")
    assert visible_tools([tool, other]) == [other]
    text = edit_image_tool.invoke({"prompt": "open the eyes"})
    assert "admins only" in text
    assert "http" not in text


def test_visible_tools_hides_both_admin_image_tools():
    tools = [
        SimpleNamespace(name=GENERATION_TOOL_NAME),
        SimpleNamespace(name=EDIT_TOOL_NAME),
        SimpleNamespace(name="weather_tool"),
    ]
    assert [t.name for t in visible_tools(tools)] == ["weather_tool"]
    set_generation_allowed(True)
    assert [t.name for t in visible_tools(tools)] == [
        GENERATION_TOOL_NAME,
        EDIT_TOOL_NAME,
        "weather_tool",
    ]


def test_edit_without_attachments_does_not_spend_budget(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []

    def _store(prompt: str, **_kwargs):
        calls.append(prompt)
        return SimpleNamespace(public_url="/images/abc")

    monkeypatch.setattr(
        "jarvis.tools.builtins.edit_image.edit_stored_image",
        _store,
    )
    set_generation_allowed(True)
    text = edit_image_tool.invoke({"prompt": "modernize the furniture"})
    assert "no attached" in text.lower()
    assert calls == []
    set_edit_reference_images([_attachment()])
    follow = edit_image_tool.invoke({"prompt": "modernize the furniture"})
    assert calls == ["modernize the furniture"]
    assert "![short alt](/images/abc)" in follow
    assert "Edited image" in follow


def test_admin_edits_one_png_and_shares_budget_with_generate(
    image_root, monkeypatch: pytest.MonkeyPatch
):
    images = _Images()
    monkeypatch.setattr(
        "jarvis.infrastructure.images.edit.openai.OpenAI",
        lambda: _Client(images),
    )
    monkeypatch.setattr(
        "jarvis.infrastructure.images.generate.openai.OpenAI",
        lambda: _Client(images),
    )
    set_generation_allowed(True)
    set_edit_reference_images([_attachment()])
    first = edit_image_tool.invoke({"prompt": "modernize the furniture"})
    second = edit_image_tool.invoke({"prompt": "open the eyes"})
    third = generate_image_tool.invoke({"prompt": "a red square"})
    assert len(images.edit_calls) == 1
    assert images.edit_calls[0]["model"] == "gpt-image-1-mini"
    assert images.edit_calls[0]["quality"] == "low"
    assert images.edit_calls[0]["size"] == "1024x1024"
    assert images.edit_calls[0]["n"] == 1
    assert images.edit_calls[0]["prompt"] == "modernize the furniture"
    image_arg = images.edit_calls[0]["image"]
    assert isinstance(image_arg, tuple)
    assert image_arg[1] == PNG
    assert "/images/" in first
    assert "already used" in second.lower()
    assert "already used" in third.lower()
    assert images.generate_calls == []
    stored = list(image_root.glob("*.png"))
    assert len(stored) == 1


def test_multi_reference_images_are_sent_as_a_list(
    image_root, monkeypatch: pytest.MonkeyPatch
):
    images = _Images()
    monkeypatch.setattr(
        "jarvis.infrastructure.images.edit.openai.OpenAI",
        lambda: _Client(images),
    )
    set_generation_allowed(True)
    set_edit_reference_images([_attachment(), _attachment()])
    text = edit_image_tool.invoke(
        {"prompt": "place the person from the first photo into the second"}
    )
    assert "/images/" in text
    assert isinstance(images.edit_calls[0]["image"], list)
    assert len(images.edit_calls[0]["image"]) == 2


def test_edit_stored_image_uses_the_year_ttl(image_root):
    stored = edit_stored_image(
        "open the eyes",
        images=[EditReferenceImage("image/png", PNG)],
        client=_Client(_Images()),
        now=NOW,
    )
    assert stored is not None
    assert stored.kind == GENERATED_KIND
    assert stored.expires_at == NOW + timedelta(days=365)


def test_edit_optional_mask_is_forwarded(monkeypatch: pytest.MonkeyPatch):
    images = _Images()
    monkeypatch.setattr(
        "jarvis.infrastructure.images.edit.openai.OpenAI",
        lambda: _Client(images),
    )
    mask = EditReferenceImage("image/png", PNG)
    edit_image_bytes(
        "open the eyes",
        [EditReferenceImage("image/png", PNG)],
        mask=mask,
        client=_Client(images),
    )
    assert "mask" in images.edit_calls[0]
    assert images.edit_calls[0]["mask"][1] == PNG


def test_provider_refusal_stays_text_only(monkeypatch: pytest.MonkeyPatch):
    images = _Images()
    images.error = openai.BadRequestError(
        "rejected",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body=None,
    )
    monkeypatch.setattr(
        "jarvis.infrastructure.images.edit.openai.OpenAI",
        lambda: _Client(images),
    )
    set_generation_allowed(True)
    set_edit_reference_images([_attachment()])
    text = edit_image_tool.invoke({"prompt": "something disallowed"})
    assert "refused" in text.lower()
    assert "http" not in text


def test_content_policy_violation_explains_safety_rules(
    monkeypatch: pytest.MonkeyPatch,
):
    images = _Images()
    images.error = openai.BadRequestError(
        "Your request was rejected as a result of our safety system.",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body={
            "code": "content_policy_violation",
            "message": "Your request was rejected as a result of our safety system.",
        },
    )
    monkeypatch.setattr(
        "jarvis.infrastructure.images.edit.openai.OpenAI",
        lambda: _Client(images),
    )
    set_generation_allowed(True)
    set_edit_reference_images([_attachment()])
    text = edit_image_tool.invoke({"prompt": "something disallowed"})
    assert "safety/content policy" in text.lower()
    assert "rephras" in text.lower()
    assert "http" not in text


def test_empty_prompt_does_not_spend_the_turn(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def _store(prompt: str, **_kwargs):
        calls.append(prompt)
        return SimpleNamespace(public_url="/images/abc")

    monkeypatch.setattr(
        "jarvis.tools.builtins.edit_image.edit_stored_image",
        _store,
    )
    set_generation_allowed(True)
    set_edit_reference_images([_attachment()])
    text = edit_image_tool.invoke({"prompt": "  "})
    follow = edit_image_tool.invoke({"prompt": "open the eyes"})
    assert "description" in text.lower()
    assert calls == ["open the eyes"]
    assert "Edited image" in follow


def test_edit_image_bytes_rejects_empty_images_and_long_prompt():
    with pytest.raises(ValueError, match="reference image"):
        edit_image_bytes("open the eyes", [], client=_Client(_Images()))
    with pytest.raises(ValueError, match="4000"):
        edit_image_bytes(
            "x" * 4001,
            [EditReferenceImage("image/png", PNG)],
            client=_Client(_Images()),
        )


def test_run_model_binds_and_clears_edit_attachments():
    seen: dict[str, object] = {}

    class _Agent:
        async def invoke(self, **_kwargs):
            seen["during"] = len(edit_reference_images())
            seen["allowed"] = generation_allowed()
            return {
                "messages": [
                    HumanMessage(content="edit"),
                    AIMessage(content="done"),
                ]
            }

    session = JarvisSession(
        ModelEnum.GPT_4O_MINI,
        "edit-admin-turn",
        user_info={
            "admin": True,
            "real_name": "Ada",
            "jarvis_name": "Sir",
            "is_female": False,
        },
    )
    session._load_or_build_agent = lambda: _Agent()  # type: ignore[method-assign]
    asyncio.run(
        session._run_model(
            [],
            images=[_attachment()],
        )
    )
    assert seen["during"] == 1
    assert seen["allowed"] is True
    assert edit_reference_images() == ()
