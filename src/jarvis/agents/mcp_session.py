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

When a tool call fails because the stdio transport died, the session marks
itself broken. The next ``aensure_ready`` closes and reopens every server so
fresh tools can be bound into a new agent graph.
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Callable

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from jarvis.core.paths import MCP_DIR, MCP_SERVER_CONFIG_PATH

logger = logging.getLogger(__name__)

_PYTHON_COMMANDS = frozenset({"python", "python3", "py", "python.exe", "python3.exe"})
_TRANSPORT_MARKERS = (
    "closed",
    "connection",
    "broken pipe",
    "eof",
    "transport",
    "stdio",
    "not connected",
)


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


def _is_transport_failure(exc: BaseException) -> bool:
    """
    Report whether ``exc`` looks like a dead MCP stdio transport.

    Args:
        exc: Exception raised from an MCP tool call.

    Returns:
        True for connection/closed-resource style failures.
    """
    if isinstance(exc, (ConnectionError, BrokenPipeError, EOFError, TimeoutError)):
        return True
    if isinstance(exc, OSError):
        return True
    nested = getattr(exc, "exceptions", None)
    if nested is not None and type(exc).__name__ in {
        "ExceptionGroup",
        "BaseExceptionGroup",
    }:
        return any(_is_transport_failure(inner) for inner in nested)
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _TRANSPORT_MARKERS)


def _with_serialized_calls(
    tool: Any,
    lock: asyncio.Lock,
    on_transport_failure: Callable[[BaseException], None],
) -> Any:
    """
    Return ``tool`` with its coroutine guarded by ``lock``.

    Args:
        tool: LangChain tool loaded from an MCP session.
        lock: Lock shared by every tool on that stdio server.
        on_transport_failure: Sync callback when a call looks like a dead transport.

    Returns:
        Tool whose ``coroutine`` waits for ``lock`` before calling the server.
        The original tool when it has no coroutine.
    """
    coroutine = getattr(tool, "coroutine", None)
    if coroutine is None:
        return tool

    async def _serialized(*args: Any, **kwargs: Any) -> Any:
        async with lock:
            try:
                return await coroutine(*args, **kwargs)
            except Exception as exc:
                if _is_transport_failure(exc):
                    on_transport_failure(exc)
                raise

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
        self._broken = False
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Return True after a successful ``aconnect`` until ``aclose``."""
        return self._connected

    @property
    def is_broken(self) -> bool:
        """Return True after a tool call saw a dead stdio transport."""
        return self._broken

    @property
    def tools(self) -> list:
        """Return a copy of the tools loaded from connected MCP servers."""
        return list(self._tools)

    def mark_broken(self, exc: BaseException | None = None) -> None:
        """
        Mark the session as needing a reconnect.

        Args:
            exc: Optional failure that triggered the mark (for logging).
        """
        if not self._broken:
            if exc is None:
                logger.warning("MCP session marked broken")
            else:
                logger.warning("MCP session marked broken: %s", exc)
        self._broken = True

    async def aconnect(self) -> list:
        """
        Start every configured MCP server and load its tools.

        Returns:
            Loaded MCP tools. Idempotent when already connected and healthy.

        Raises:
            OSError: If ``server_config.json`` cannot be read.
            json.JSONDecodeError: If the config file is not valid JSON.
        """
        async with self._lock:
            if self._connected and not self._broken:
                logger.info("MCP services are already connected")
                return self.tools
            if self._connected and self._broken:
                await self._aclose_unlocked()
            return await self._aconnect_unlocked()

    async def aensure_ready(self) -> list:
        """
        Ensure servers are connected, reconnecting when the session is broken.

        Returns:
            Loaded MCP tools after a healthy connect.

        Raises:
            OSError: If ``server_config.json`` cannot be read.
            json.JSONDecodeError: If the config file is not valid JSON.
        """
        if self._connected and not self._broken:
            return self.tools
        if self._broken:
            logger.info("Reconnecting MCP services after transport failure")
            return await self.areconnect()
        return await self.aconnect()

    async def areconnect(self) -> list:
        """
        Close every MCP server and connect again.

        Returns:
            Freshly loaded MCP tools.
        """
        async with self._lock:
            await self._aclose_unlocked()
            return await self._aconnect_unlocked()

    async def _aconnect_unlocked(self) -> list:
        """Open servers while ``self._lock`` is already held."""
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
            self._broken = False
            return self.tools
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._tools = []
            self._call_locks = []
            self._connected = False
            self._broken = False
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
        self._tools.extend(
            _with_serialized_calls(tool, call_lock, self.mark_broken)
            for tool in mcp_tools
        )

    async def aclose(self) -> None:
        """
        Close MCP sessions and drop loaded tools.

        Returns:
            None. Safe to call when the session was never opened.
        """
        async with self._lock:
            await self._aclose_unlocked()

    async def _aclose_unlocked(self) -> None:
        """Close servers while ``self._lock`` is already held."""
        for call_lock in list(self._call_locks):
            async with call_lock:
                pass
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._tools = []
        self._call_locks = []
        self._connected = False
        self._broken = False


_mcp_tool_session = McpToolSession()


def get_mcp_tool_session() -> McpToolSession:
    """Return the process-wide MCP tool session."""
    return _mcp_tool_session
