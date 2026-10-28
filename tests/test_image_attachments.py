"""Image attachment shaping, history budget, and POST /ask validation."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from jarvis.agents.graph import compile_tool_agent
from jarvis.agents.session.orchestrator import JarvisSession
from jarvis.api.app import app
from jarvis.core.config import JWT_ALGORITHM
from jarvis.core.enums import ModelEnum
from jarvis.domain.chat.chat_state import ChatState
from jarvis.domain.users.prompts import get_welcome_message
from jarvis.infrastructure.images import (
    MAX_IMAGES_PER_TURN,
    OMITTED_IMAGE_NOTE,
    ImageAttachmentError,
    VisionNotSupportedError,
    build_human_message,
    normalize_image_attachments,
    prepare_messages_for_model,
)

TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _user() -> dict:
    return {
        "real_name": "Ada",
        "jarvis_name": "Ada",
        "is_female": False,
        "admin": False,
    }


def _token() -> str:
    payload = {
        "sub": "pytest-user",
        "real_name": "Pytest User",
        "jarvis_name": "Sir",
        "is_female": False,
        "admin": False,
        "exp": 9999999999,
    }
    secret = __import__("os").environ["JWT_SECRET_KEY"]
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _png(count: int = 1) -> list[dict[str, str]]:
    return [
        {"media_type": "image/png", "data_base64": TINY_PNG} for _ in range(count)
    ]


def test_normalize_rejects_too_many_images() -> None:
    with pytest.raises(ImageAttachmentError) as exc:
        normalize_image_attachments(_png(MAX_IMAGES_PER_TURN + 1))
    assert exc.value.code == "too_many_images"


def test_normalize_rejects_bad_base64() -> None:
    with pytest.raises(ImageAttachmentError) as exc:
        normalize_image_attachments(
            [{"media_type": "image/png", "data_base64": "not base64"}]
        )
    assert exc.value.code == "invalid_base64"


def test_normalize_accepts_data_url() -> None:
    images = normalize_image_attachments(
        [
            {
                "media_type": "image/png",
                "data_base64": f"data:image/png;base64,{TINY_PNG}",
            }
        ]
    )
    assert images[0]["media_type"] == "image/png"
    assert images[0]["data_base64"] == TINY_PNG


def test_build_human_message_text_only() -> None:
    message = build_human_message("hello")
    assert message.content == "hello"


def test_build_human_message_includes_image_block() -> None:
    message = build_human_message("look", _png())
    assert isinstance(message.content, list)
    assert message.content[0] == {"type": "text", "text": "look"}
    assert message.content[1]["type"] == "image_url"
    assert message.content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_build_human_message_image_only_uses_default_prompt() -> None:
    message = build_human_message("  ", _png())
    assert message.content[0]["text"].startswith("Please look at")


def test_prepare_messages_keeps_only_latest_image() -> None:
    older = build_human_message("first", _png())
    latest = build_human_message("second", _png())
    prepared = prepare_messages_for_model(
        [older, AIMessage(content="ack"), latest]
    )
    assert isinstance(prepared[0].content, str)
    assert OMITTED_IMAGE_NOTE in prepared[0].content
    assert prepared[2].content == latest.content


def test_graph_omits_older_images_on_later_turns() -> None:
    seen: list[list] = []

    class _RecordingLLM:
        def bind_tools(self, tools: list) -> "_RecordingLLM":
            return self

        def invoke(self, messages: list) -> AIMessage:
            seen.append(list(messages))
            return AIMessage(content="ack")

    graph, _saver = compile_tool_agent(
        _RecordingLLM(), [], checkpointer=MemorySaver()
    )
    config = {"configurable": {"thread_id": "images"}}
    graph.invoke(
        {
            "messages": [build_human_message("first", _png())],
            "real_name": "Ada",
        },
        config,
    )
    graph.invoke(
        {
            "messages": [build_human_message("second", _png())],
            "real_name": "Ada",
        },
        config,
    )
    humans = [msg for msg in seen[1] if isinstance(msg, HumanMessage)]
    assert isinstance(humans[0].content, str)
    assert OMITTED_IMAGE_NOTE in humans[0].content
    assert isinstance(humans[-1].content, list)
    assert humans[-1].content[0]["text"] == "second"


def test_non_vision_model_rejects_images_without_advancing_state() -> None:
    session = JarvisSession(ModelEnum.GPT_3_5, "no-vision-images", user_info=_user())
    with pytest.raises(VisionNotSupportedError):
        asyncio.run(session.handle_turn("look", images=_png()))
    assert session._chat_state == ChatState.NOT_INITIALIZED


def test_welcome_turn_still_sends_images_to_the_model() -> None:
    user = _user()
    session = JarvisSession(ModelEnum.GPT_4O_MINI, "welcome-images", user_info=user)
    captured: dict = {}

    async def _fake(messages: list) -> list[str]:
        captured["messages"] = messages
        return ["a red square"]

    session._run_model = _fake  # type: ignore[method-assign]
    replies = asyncio.run(session.handle_turn("look", images=_png()))
    assert replies[0] == get_welcome_message(user)
    assert replies[1] == "a red square"
    assert session._chat_state == ChatState.STARTING_CHAT
    human = captured["messages"][-1]
    assert isinstance(human, HumanMessage)
    assert any(
        isinstance(block, dict) and block.get("type") == "image_url"
        for block in human.content
    )


def test_ask_rejects_empty_turn() -> None:
    client = TestClient(app)
    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "  "},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_ask_rejects_too_many_images() -> None:
    client = TestClient(app)
    response = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"message": "look", "images": _png(5)},
    )
    assert response.status_code == 400
    assert "4" in response.json()["detail"]


def test_ask_image_only_calls_session_with_attachments() -> None:
    client = TestClient(app)
    fake = AsyncMock(return_value=["described"])
    with patch("jarvis.api.services.chat_service.ask_jarvis", fake):
        response = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {_token()}"},
            json={"message": "", "images": _png()},
        )
    assert response.status_code == 200
    assert response.json() == {"response": ["described"]}
    assert fake.await_args.kwargs["images"][0]["media_type"] == "image/png"
