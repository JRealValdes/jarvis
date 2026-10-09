"""Process-wide MCP stdio sessions that supply extra agent tools.

The session stays open for the life of the process. It is opened from the
API lifespan, the CLI, or the first async turn, and closed on shutdown and
when the agent cache is reset.

Tool coroutines are bound to the event loop that opened the session. Callers
on that loop must use ``ainvoke`` / ``aask_jarvis``. Do not wrap each turn in
``asyncio.run``: that closes the loop and drops the stdio processes.

Tools from one server share a lock, so concurrent turns wait instead of
writing to the same stdio session at once. A bare ``python`` command in the
config is replaced with the interpreter that is running Jarvis.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from jarvis.core.paths import MCP_DIR, MCP_SERVER_CONFIG_PATH

logger = logging.getLogger(__name__)

_PYTHON_COMMANDS = frozenset({"python", "python3", "py", "python.exe", "python3.exe"})


def _resolve_mcp_server_config(server_config: dict) -> dict:
    """
    Normalize an MCP server entry for this process.

    Relative ``.py`` arguments are resolved under ``MCP_DIR``. A bare Python
    command (``python``, ``python3``, ``py``) is replaced with the interpreter
    that is running Jarvis, so the server sees the project environment.

    Args:
        server_config: Raw entry from ``server_config.json``.

    Returns:
        Config with an absolute interpreter and absolute script paths.
    """
    resolved = dict(server_config)
    command = resolved.get("command")
    if isinstance(command, str) and command.lower() in _PYTHON_COMMANDS:
        resolved["command"] = sys.executable
    args = list(resolved.get("args", []))
    normalized: list[str] = []
    for arg in args:
        if isinstance(arg, str) and arg.endswith(".py") and not os.path.isabs(arg):
            normalized.append(str((MCP_DIR / arg).resolve()))
        else:
            normalized.append(arg)
    resolved["args"] = normalized
    return resolved


def _with_serialized_calls(tool: Any, lock: asyncio.Lock) -> Any:
    """
    Return ``tool`` with its coroutine guarded by ``lock``.

    Args:
        tool: LangChain tool loaded from an MCP session.
        lock: Lock shared by every tool on that stdio server.

    Returns:
        Tool whose ``coroutine`` waits for ``lock`` before calling the server.
        The original tool when it has no coroutine.
    """
    coroutine = getattr(tool, "coroutine", None)
    if coroutine is None:
        return tool

    async def _serialized(*args: Any, **kwargs: Any) -> Any:
        async with lock:
            return await coroutine(*args, **kwargs)

    if hasattr(tool, "model_copy"):
        return tool.model_copy(update={"coroutine": _serialized})
    tool.coroutine = _serialized
    return tool


class McpToolSession:
    """
    Stdio connections to every server in ``data/mcp/server_config.json``.

    One instance is shared by every agent in the process. Agents do not close
    it; ``aclose`` is for shutdown and cache reset.
    """

    def __init__(self) -> None:
        self._exit_stack: AsyncExitStack | None = None
        self._tools: list = []
        self._call_locks: list[asyncio.Lock] = []
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Return True after a successful ``aconnect`` until ``aclose``."""
        return self._connected

    @property
    def tools(self) -> list:
        """Return a copy of the tools loaded from connected MCP servers."""
        return list(self._tools)

    async def aconnect(self) -> list:
        """
        Start every configured MCP server and load its tools.

        Returns:
            Loaded MCP tools. Idempotent when already connected.

        Raises:
            OSError: If ``server_config.json`` cannot be read.
            json.JSONDecodeError: If the config file is not valid JSON.
        """
        async with self._lock:
            if self._connected:
                logger.info("MCP services are already connected")
                return self.tools

            self._exit_stack = AsyncExitStack()
            try:
                await self._exit_stack.__aenter__()
                self._tools = []
                self._call_locks = []
                with open(MCP_SERVER_CONFIG_PATH, "r", encoding="utf-8") as file:
                    data = json.load(file)
                servers = data.get("mcpServers", {})
                for server_name, server_config in servers.items():
                    await self._connect_to_server(server_name, server_config)
                self._connected = True
                return self.tools
            except Exception:
                await self._exit_stack.aclose()
                self._exit_stack = None
                self._tools = []
                self._call_locks = []
                self._connected = False
                raise

    async def _connect_to_server(self, server_name: str, server_config: dict) -> None:
        """
        Connect to one MCP server over stdio and append its tools.

        Args:
            server_name: Logical server name (for logging).
            server_config: Parameters for ``StdioServerParameters``.
        """
        if self._exit_stack is None:
            raise RuntimeError("MCP exit stack is not open.")
        logger.info("Connecting MCP server %s", server_name)
        call_lock = asyncio.Lock()
        self._call_locks.append(call_lock)
        server_params = StdioServerParameters(**_resolve_mcp_server_config(server_config))
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        mcp_tools = await load_mcp_tools(session)
        self._tools.extend(_with_serialized_calls(tool, call_lock) for tool in mcp_tools)

    async def aclose(self) -> None:
        """
        Close MCP sessions and drop loaded tools.

        Returns:
            None. Safe to call when the session was never opened.
        """
        async with self._lock:
            for call_lock in list(self._call_locks):
                async with call_lock:
                    pass
            if self._exit_stack is not None:
                await self._exit_stack.aclose()
            self._exit_stack = None
            self._tools = []
            self._call_locks = []
            self._connected = False


_mcp_tool_session = McpToolSession()


def get_mcp_tool_session() -> McpToolSession:
    """Return the process-wide MCP tool session."""
    return _mcp_tool_session
