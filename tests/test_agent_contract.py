"""Agent protocol, MCP session lifecycle, and factory guards (no network)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.agents.factory import build_agent
from jarvis.agents.mcp_session import McpToolSession, _resolve_mcp_server_config
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
    assert Path(script).is_absolute()
    assert script.endswith("math_server.py")
    assert resolved["args"][1] == "--flag"


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
