"""SQLite conversation checkpoints survive a reopen and honor reset (no network)."""

import asyncio
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from jarvis.agents.checkpointer import open_model_checkpointer
from jarvis.agents.graph import compile_tool_agent
from jarvis.agents.implementations.memory import JarvisMemoryAgent
from jarvis.agents.session import reset_cache, reset_session
from jarvis.core.enums import ModelEnum


class _FakeLLM:
    """Chat model stand-in that acknowledges every turn without tools."""

    def bind_tools(self, tools: list) -> "_FakeLLM":
        """Return self so the graph can bind an empty tool list."""
        return self

    def invoke(self, messages: list) -> AIMessage:
        """Return a fixed assistant message."""
        return AIMessage(content="ack")


def _human_contents(state: dict) -> list[str]:
    """Return human message texts from a graph state."""
    return [
        message.content
        for message in state["messages"]
        if isinstance(message, HumanMessage)
    ]


def _invoke(graph: object, text: str, thread_id: str) -> dict:
    """Send one human turn to ``graph`` on ``thread_id``."""
    return graph.invoke(
        {"messages": [HumanMessage(content=text)], "real_name": "Ada"},
        {"configurable": {"thread_id": thread_id}},
    )


def test_thread_survives_reopen_and_reset_session_drops_it():
    opened = open_model_checkpointer(ModelEnum.GPT_4O_MINI)
    try:
        graph, _saver = compile_tool_agent(
            _FakeLLM(), [], checkpointer=opened.saver
        )
        _invoke(graph, "one", "ada")
    finally:
        opened.close()

    reopened = open_model_checkpointer(ModelEnum.GPT_4O_MINI)
    try:
        graph, _saver = compile_tool_agent(
            _FakeLLM(), [], checkpointer=reopened.saver
        )
        state = _invoke(graph, "two", "ada")
        assert _human_contents(state) == ["one", "two"]
    finally:
        reopened.close()

    reset_session("ada", ModelEnum.GPT_4O_MINI)

    after_reset = open_model_checkpointer(ModelEnum.GPT_4O_MINI)
    try:
        graph, _saver = compile_tool_agent(
            _FakeLLM(), [], checkpointer=after_reset.saver
        )
        state = _invoke(graph, "three", "ada")
        assert _human_contents(state) == ["three"]
    finally:
        after_reset.close()


@patch("jarvis.agents.implementations.memory.ChatOpenAI")
def test_ainvoke_persists_thread_and_delete_drops_it(mock_chat_openai: MagicMock):
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_llm
    fake_llm.invoke.return_value = AIMessage(content="ack")
    mock_chat_openai.return_value = fake_llm

    async def _turn(agent: JarvisMemoryAgent, text: str) -> dict:
        return await agent.invoke(
            input={"messages": [HumanMessage(content=text)], "real_name": "Ada"},
            config={"configurable": {"thread_id": "ada"}},
        )

    async def _run() -> None:
        opened = JarvisMemoryAgent(ModelEnum.GPT_4O_MINI)
        try:
            state = await _turn(opened, "one")
            assert _human_contents(state) == ["one"]
        finally:
            await opened.cleanup()

        reopened = JarvisMemoryAgent(ModelEnum.GPT_4O_MINI)
        try:
            state = await _turn(reopened, "two")
            assert _human_contents(state) == ["one", "two"]
            reopened.memory.delete_thread("ada")
            state = await _turn(reopened, "three")
            assert _human_contents(state) == ["three"]
        finally:
            await reopened.cleanup()

    asyncio.run(_run())


def test_reset_cache_deletes_checkpoint_files():
    opened = open_model_checkpointer(ModelEnum.GPT_3_5)
    path = opened.path
    opened.close()
    assert path.is_file()

    asyncio.run(reset_cache())

    assert not path.exists()
