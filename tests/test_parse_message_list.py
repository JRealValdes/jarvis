"""Unit tests for chat history parsing and tool-trace visibility."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from jarvis.agents.session.history import parse_message_list


def _tool_call_ai(name: str, arguments: str = "{}") -> AIMessage:
    """Build an AIMessage that requests a tool call (OpenAI additional_kwargs)."""
    return AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            ]
        },
    )


def test_parse_hides_tool_traces_by_default() -> None:
    messages = [
        HumanMessage(content="search something"),
        _tool_call_ai("web_search_tool", '{"query": "x"}'),
        ToolMessage(content="big payload", name="web_search_tool", tool_call_id="call_1"),
        AIMessage(content="Here is the answer."),
    ]
    parsed = parse_message_list(messages, show_tool_traces=False)
    assert parsed == [
        {"role": "user", "content": "search something"},
        {"role": "assistant", "content": "Here is the answer."},
    ]


def test_parse_shows_all_tools_equally_when_enabled() -> None:
    messages = [
        HumanMessage(content="check calendar"),
        _tool_call_ai("get_upcoming_events_tool"),
        ToolMessage(
            content="[]",
            name="get_upcoming_events_tool",
            tool_call_id="call_1",
        ),
        _tool_call_ai("web_search_tool", '{"query": "news"}'),
        ToolMessage(content="hits", name="web_search_tool", tool_call_id="call_1"),
        AIMessage(content="Done."),
    ]
    parsed = parse_message_list(messages, show_tool_traces=True)
    assert parsed[0] == {"role": "user", "content": "check calendar"}
    assert parsed[1]["content"].startswith(
        "Calling function: get_upcoming_events_tool."
    )
    assert parsed[2] == {
        "role": "assistant",
        "content": "Function result get_upcoming_events_tool: []",
    }
    assert "web_search_tool" in parsed[3]["content"]
    assert parsed[4] == {
        "role": "assistant",
        "content": "Function result web_search_tool: hits",
    }
    assert parsed[5] == {"role": "assistant", "content": "Done."}


def test_parse_with_args_formats_arguments() -> None:
    messages = [_tool_call_ai("calc_tool", '{"expression": "1+1"}')]
    parsed = parse_message_list(messages, show_tool_traces=True)
    assert parsed == [
        {
            "role": "assistant",
            "content": "Calling function: calc_tool. Arguments: expression=1+1",
        }
    ]


def test_parse_keeps_content_on_tool_call_message_when_traces_off() -> None:
    msg = AIMessage(
        content="I will look that up.",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search_tool", "arguments": "{}"},
                }
            ]
        },
    )
    parsed = parse_message_list([msg], show_tool_traces=False)
    assert parsed == [{"role": "assistant", "content": "I will look that up."}]
