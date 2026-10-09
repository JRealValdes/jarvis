"""Shared LangGraph wiring for tool-calling Jarvis agents."""

from typing import Annotated, Any

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


class AgentState(TypedDict):
    """Graph state: accumulated messages and ``real_name`` for tools."""

    messages: Annotated[list, add_messages]
    real_name: str


def compile_tool_agent(
    llm: Any,
    tools: list,
    *,
    checkpointer: MemorySaver | None = None,
) -> tuple[Any, MemorySaver]:
    """
    Compile the chatbot ↔ tools graph used by Jarvis agents.

    Args:
        llm: Chat model that supports ``bind_tools``.
        tools: Tools available to the model.
        checkpointer: Thread store. A new ``MemorySaver`` is created when omitted.

    Returns:
        Tuple of (compiled graph, checkpointer).
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph_builder = StateGraph(AgentState)
    llm_with_tools = llm.bind_tools(tools)

    def chatbot(state: AgentState) -> dict:
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools=tools))
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.set_entry_point("chatbot")
    graph = graph_builder.compile(checkpointer=checkpointer)
    return graph, checkpointer
