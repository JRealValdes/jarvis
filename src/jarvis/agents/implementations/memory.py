"""LangGraph agent with a SQLite checkpointer and tools for OpenAI chat models."""

import asyncio
from typing import Any

from langchain_openai import ChatOpenAI

from jarvis.agents.checkpointer import (
    AsyncSqliteCheckpoint,
    aopen_model_checkpointer,
    delete_persisted_thread,
)
from jarvis.agents.graph import compile_tool_agent
from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import resolve_openai_chat_model_id
from jarvis.tools import local_tools


class _CheckpointMemory:
    """Delete one thread from the model's checkpoint file."""

    def __init__(self, model_enum: ModelEnum) -> None:
        """
        Args:
            model_enum: Model whose checkpoint file holds the thread.
        """
        self._model_enum = model_enum

    def delete_thread(self, thread_id: str) -> None:
        """
        Delete every stored checkpoint for ``thread_id``.

        Uses a short-lived sync connection so this can run on the same loop
        that owns the async saver. ``AsyncSqliteSaver.delete_thread`` refuses
        that loop.

        Args:
            thread_id: Conversation id to remove.
        """
        delete_persisted_thread(self._model_enum, thread_id)


class JarvisMemoryAgent:
    """
    Agent with a chatbot ↔ tools loop and a SQLite checkpointer.

    The graph is compiled on first use with ``AsyncSqliteSaver``, on the loop
    that calls ``invoke``. MCP tools, when enabled, are passed in by the
    factory. This class does not open or close the process-wide MCP session.
    ``cleanup`` closes the aiosqlite connection only.

    Attributes:
        model_enum: OpenAI-backed ModelEnum (e.g. GPT_4O_MINI, GPT_3_5).
        graph: Compiled graph, or None until ``ensure_ready``.
        memory: Thread deleter for this model's checkpoint file.
        tools: Tools bound into the graph.
    """

    def __init__(self, model_enum: ModelEnum, tools: list | None = None) -> None:
        """
        Args:
            model_enum: OpenAI chat ModelEnum member.
            tools: Tools to bind. Defaults to the local tool registry.

        Raises:
            ValueError: If the model is not an OpenAI chat model.
        """
        self.model_enum = model_enum
        self.tools = list(local_tools if tools is None else tools)
        self._llm = ChatOpenAI(
            model=resolve_openai_chat_model_id(model_enum),
            temperature=0,
        )
        self.graph: Any = None
        self.memory: _CheckpointMemory = _CheckpointMemory(model_enum)
        self._checkpoint: AsyncSqliteCheckpoint | None = None
        self._open_lock: asyncio.Lock | None = None

    def _lock(self) -> asyncio.Lock:
        """
        Return the lock that serializes open and close.

        Returns:
            Lock created on the running loop.
        """
        if self._open_lock is None:
            self._open_lock = asyncio.Lock()
        return self._open_lock

    async def ensure_ready(self) -> None:
        """
        Compile the graph with an async SQLite checkpointer if needed.

        Returns:
            None. Safe to call more than once.
        """
        if self.graph is not None:
            return
        async with self._lock():
            if self.graph is not None:
                return
            opened = await aopen_model_checkpointer(self.model_enum)
            self._checkpoint = opened
            self.graph, _saver = compile_tool_agent(
                self._llm, self.tools, checkpointer=opened.saver
            )

    async def invoke(self, **kwargs: Any) -> dict:
        """
        Invoke the graph on the caller's event loop.

        Args:
            **kwargs: ``input``, ``config``, etc.

        Returns:
            Final graph state.
        """
        await self.ensure_ready()
        return await self.graph.ainvoke(**kwargs)

    async def cleanup(self) -> None:
        """Close the aiosqlite connection. Does not close the shared MCP session."""
        async with self._lock():
            checkpoint = self._checkpoint
            self._checkpoint = None
            self.graph = None
            if checkpoint is not None:
                await checkpoint.close()
