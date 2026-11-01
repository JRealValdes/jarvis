"""Tool failures should reach the LLM as tool results, not abort the turn."""

from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from langgraph.checkpoint.memory import MemorySaver

from jarvis.agents.graph import compile_tool_agent
from jarvis.agents.session.orchestrator import JarvisSession
from jarvis.core.enums import ModelEnum
from jarvis.tools.errors import format_tool_failure, handle_tool_node_error


@tool
def _boom_tool(query: str = "") -> str:
    """Always raise so ToolNode must soft-handle the error."""
    raise RuntimeError(f"boom:{query}")


@tool
def _tool_exception_tool(query: str = "") -> str:
    """Raise ToolException like speech_to_text_tool does for Gradio callers."""
    raise ToolException(f"transcription failed:{query}")


class _ScriptedLLM:
    """LLM that calls a named tool once, then answers with the tool result."""

    def __init__(self, tool_name: str, tool_args: dict | None = None) -> None:
        self.tool_name = tool_name
        self.tool_args = tool_args or {"query": "x"}
        self.calls = 0
        self.last_messages: list = []

    def bind_tools(self, tools: list) -> "_ScriptedLLM":
        return self

    def invoke(self, messages: list) -> AIMessage:
        self.calls += 1
        self.last_messages = list(messages)
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": self.tool_args,
                        "id": "call-fail-1",
                        "type": "tool_call",
                    }
                ],
            )
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        assert tool_msgs, "expected a ToolMessage after the failing tool"
        return AIMessage(content=f"explained:{tool_msgs[-1].content}")


def test_format_tool_failure_includes_hint_and_truncates_reason():
    text = format_tool_failure(
        what="Weather lookup",
        reason="x" * 600,
        hint="Tell the user to retry.",
    )
    assert text.startswith("Weather lookup failed.")
    assert "…" in text
    assert "Tell the user to retry." in text
    assert len(text) < 700


def test_handle_tool_node_error_includes_exception_type():
    text = handle_tool_node_error(ValueError("bad args"))
    assert "ValueError" in text
    assert "bad args" in text
    assert "Do not invent" in text


def test_tool_node_surfaces_raised_errors_and_continues():
    llm = _ScriptedLLM("_boom_tool")
    graph, _saver = compile_tool_agent(
        llm, [_boom_tool], checkpointer=MemorySaver()
    )
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="please fail")],
            "real_name": "Ada",
        },
        {"configurable": {"thread_id": "tool-error-soft"}},
    )
    messages = result["messages"]
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert "RuntimeError" in tool_msgs[0].content
    assert "boom:x" in tool_msgs[0].content
    assert isinstance(messages[-1], AIMessage)
    assert messages[-1].content.startswith("explained:")
    assert llm.calls == 2


def test_tool_node_surfaces_tool_exception_and_continues():
    llm = _ScriptedLLM("_tool_exception_tool")
    graph, _saver = compile_tool_agent(
        llm, [_tool_exception_tool], checkpointer=MemorySaver()
    )
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="transcribe")],
            "real_name": "Ada",
        },
        {"configurable": {"thread_id": "tool-exception-soft"}},
    )
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert "ToolException" in tool_msgs[0].content
    assert "transcription failed:x" in tool_msgs[0].content
    assert result["messages"][-1].content.startswith("explained:")


def test_run_model_fallback_does_not_dump_raw_exception():
    class _FailingAgent:
        async def invoke(self, **_kwargs):
            raise RuntimeError("secret stack detail that must not leak")

    session = JarvisSession(
        ModelEnum.GPT_4O_MINI,
        "fallback-turn",
        user_info={"admin": False, "real_name": "Ada", "jarvis_name": "Sir", "is_female": False},
    )
    session._load_or_build_agent = lambda: _FailingAgent()  # type: ignore[method-assign]
    replies = asyncio.run(session._run_model([]))
    assert len(replies) == 1
    assert "unexpected problem" in replies[0].lower()
    assert "RuntimeError" in replies[0]
    assert "secret stack detail" not in replies[0]
    assert "There was an error processing your request" not in replies[0]
