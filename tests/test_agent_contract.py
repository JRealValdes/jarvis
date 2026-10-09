"""Agent protocol, MCP session lifecycle, and factory guards (no network)."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.agents.factory import build_agent
from jarvis.agents.mcp_session import (
    McpToolSession,
    _resolve_mcp_server_config,
    _with_serialized_calls,
)
from jarvis.agents.session import areset_cache, ask_jarvis, reset_cache
from jarvis.agents.session.cache import get_agents_cache
from jarvis.core.enums import ModelEnum


def test_build_agent_rejects_unknown_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "jarvis.agents.factory.is_openai_chat_model", lambda _model: False
    )
    with pytest.raises(ValueError, match="Unsupported model"):
        build_agent(ModelEnum.GPT_4O_MINI)


def test_build_agent_requires_connected_mcp_session(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("jarvis.agents.factory.USE_MCP", True)
    with pytest.raises(RuntimeError, match="not connected"):
        build_agent(ModelEnum.GPT_4O_MINI)


def test_ask_jarvis_refuses_sync_call_when_mcp_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("jarvis.agents.session.orchestrator.USE_MCP", True)
    with pytest.raises(RuntimeError, match="aask_jarvis"):
        ask_jarvis("hello")


def test_ask_jarvis_refuses_call_inside_running_loop(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("jarvis.agents.session.orchestrator.USE_MCP", False)

    async def _inside_loop() -> None:
        with pytest.raises(RuntimeError, match="event loop"):
            ask_jarvis("hello")

    asyncio.run(_inside_loop())


def test_mcp_session_aclose_when_disconnected():
    session = McpToolSession()
    asyncio.run(session.aclose())
    assert session.is_connected is False
    assert session.tools == []


def test_resolve_mcp_server_config_makes_script_absolute():
    resolved = _resolve_mcp_server_config(
        {"command": "python", "args": ["servers/math_server.py", "--flag"]}
    )
    script = resolved["args"][0]
    assert resolved["command"] == sys.executable
    assert Path(script).is_absolute()
    assert script.endswith("math_server.py")
    assert resolved["args"][1] == "--flag"


def test_resolve_mcp_server_config_keeps_explicit_interpreter(tmp_path: Path):
    custom = str(tmp_path / "python.exe")
    resolved = _resolve_mcp_server_config({"command": custom, "args": []})
    assert resolved["command"] == custom


def test_mcp_tool_calls_on_one_server_do_not_overlap():
    order: list[str] = []
    release = asyncio.Event()

    async def slow(*_args: object, **_kwargs: object) -> str:
        order.append("start")
        if len(order) == 1:
            await release.wait()
        order.append("end")
        return "ok"

    class _Tool:
        def __init__(self) -> None:
            self.coroutine = slow

        def model_copy(self, *, update: dict) -> "_Tool":
            clone = _Tool()
            clone.coroutine = update["coroutine"]
            return clone

    wrapped = _with_serialized_calls(_Tool(), asyncio.Lock())

    async def _run() -> None:
        first = asyncio.create_task(wrapped.coroutine())
        await asyncio.sleep(0)
        second = asyncio.create_task(wrapped.coroutine())
        await asyncio.sleep(0)
        assert order == ["start"]
        release.set()
        await asyncio.gather(first, second)

    asyncio.run(_run())
    assert order == ["start", "end", "start", "end"]


def test_areset_cache_closes_mcp_and_agents():
    agent = MagicMock()
    session = MagicMock()
    session.aclose = AsyncMock()
    get_agents_cache()[ModelEnum.GPT_4O_MINI] = agent
    try:
        with patch(
            "jarvis.agents.session.cache.get_mcp_tool_session", return_value=session
        ):
            asyncio.run(areset_cache())
        agent.cleanup.assert_called_once()
        session.aclose.assert_awaited()
        assert get_agents_cache() == {}
    finally:
        reset_cache()


def test_reset_cache_closes_mcp_without_running_loop():
    session = MagicMock()
    session.is_connected = True
    session.aclose = AsyncMock()
    with patch("jarvis.agents.session.cache.get_mcp_tool_session", return_value=session):
        reset_cache()
    session.aclose.assert_awaited()
