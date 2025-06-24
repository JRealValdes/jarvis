import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # Adjust the path to include the parent directory

from typing import Annotated
from typing_extensions import TypedDict
from enums.core_enums import ModelEnum
from langchain_openai import ChatOpenAI
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from contextlib import AsyncExitStack

local_tools = [calculate_tool, speech_to_text_tool]

class State(TypedDict):
    messages: Annotated[list, add_messages]

script_dir = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.abspath(os.path.join(script_dir, "..", "mcp", "servers", "math_server.py"))

command = "python"
command_args = [script_path]

class AgentWithMCP:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session = None
        self.llm = None
        self.tools = None
        self.graph = None
        self.memory = None
        self.thread_id = "1"  # Parameterize this in the future

    def _create_agent_with_memory(self, llm, tools):
        graph_builder = StateGraph(State)
        llm_with_tools = llm.bind_tools(tools)

        def chatbot(state: State):
            return {"messages": [llm_with_tools.invoke(state["messages"])]}

        graph_builder.add_node("chatbot", chatbot)

        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_conditional_edges(
            "chatbot",
            tools_condition,
        )
        graph_builder.add_edge("tools", "chatbot")
        graph_builder.set_entry_point("chatbot")
        self.memory = MemorySaver()
        self.graph = graph_builder.compile(checkpointer=self.memory)

    def _build_agent_kwargs(self, messages: list) -> dict:
        kwargs = {"input": {"messages": messages}}
        kwargs["config"] = {"configurable": {"thread_id": self.thread_id}}
        return kwargs

    async def setup(self):
        server_params = StdioServerParameters(command=command, args=command_args)
        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

        mcp_tools = await load_mcp_tools(self.session)
        local_tools = [calculate_tool, speech_to_text_tool]
        self.tools = mcp_tools + local_tools
        self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        self._create_agent_with_memory(self.llm, self.tools)

    async def invoke(self, prompt: str):
        kwargs = {
            "input": {"messages": [HumanMessage(content=prompt)]},
            "config": {"configurable": {"thread_id": self.thread_id}},
        }
        result = await self.graph.ainvoke(**kwargs)
        return result

    async def close(self):
        await self.exit_stack.aclose()

async def main():
    agent = AgentWithMCP()
    await agent.setup()

    try:
        result = await agent.invoke("Me llamo Javier")
        result = await agent.invoke("¿Cómo me llamo?")
        for msg in result["messages"]:
            print("Jarvis:", msg.content)
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
