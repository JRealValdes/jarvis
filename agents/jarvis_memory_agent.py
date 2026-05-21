"""LangGraph agent with memory (MemorySaver) and tools for GPT-3.5."""

from typing import Annotated

from typing_extensions import TypedDict

from core.enums import ModelEnum
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from tools.tools_registry import local_tools


class State(TypedDict):
    """Graph state: accumulated messages and real_name for tools."""

    messages: Annotated[list, add_messages]
    real_name: str


class JarvisMemoryAgent:
    """
    Agent with chatbot ↔ tools loop and in-memory checkpointer.

    Attributes:
        model_enum: Must be GPT_3_5.
        graph: Compiled graph.
        memory: MemorySaver for per-thread_id threads.
        tools: Registered local tools.
    """

    def __init__(self, model_enum: ModelEnum) -> None:
        """
        Args:
            model_enum: Only ModelEnum.GPT_3_5 is supported.

        Raises:
            ValueError: If the model is not GPT_3_5.
        """
        self.model_enum = model_enum
        self.graph, self.memory, self.tools = self._build_agent(model_enum)

    def _build_agent(
        self, model_enum: ModelEnum
    ) -> tuple[object, MemorySaver, list]:
        """
        Compile the StateGraph with chatbot and tools nodes.

        Args:
            model_enum: LLM model.

        Returns:
            Tuple (compiled graph, memory saver, tool list).

        Raises:
            ValueError: If model_enum is not GPT_3_5.
        """
        tools = local_tools
        if model_enum == ModelEnum.GPT_3_5:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        else:
            raise ValueError(f"Unsupported model: {model_enum}")

        graph_builder = StateGraph(State)
        llm_with_tools = llm.bind_tools(tools)

        def chatbot(state: State) -> dict:
            return {"messages": [llm_with_tools.invoke(state["messages"])]}

        graph_builder.add_node("chatbot", chatbot)
        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        graph_builder.set_entry_point("chatbot")

        memory = MemorySaver()
        graph = graph_builder.compile(checkpointer=memory)
        return graph, memory, tools

    def invoke(self, **kwargs) -> dict:
        """
        Invoke the graph (requires config with thread_id when memory is enabled).

        Args:
            **kwargs: ``input``, ``config``, etc.

        Returns:
            Final graph state.
        """
        return self.graph.invoke(**kwargs)

    def cleanup(self) -> None:
        """Release agent resources (no-op)."""
        pass
