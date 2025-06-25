import os
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Annotated
from typing_extensions import TypedDict
from enums.core_enums import ModelEnum
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

local_tools = [calculate_tool, speech_to_text_tool]

class State(TypedDict):
    messages: Annotated[list, add_messages]

server_config_path = "mcp\server_config.json"

class JarvisMcpMemoryAgent:
    def __init__(self, model_enum: ModelEnum):
        self.model_enum = model_enum
        self.exit_stack = None
        self.tools = None
        self.graph = None
        self.memory = None
        self._is_connected = False
        self.sessions_to_tools = {}

    def _create_langgraph_agent(self, model_enum: ModelEnum, tools, memory=None):
        if model_enum == ModelEnum.GPT_3_5:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        else:
            raise ValueError(f"Unsupported model: {model_enum}")

        graph_builder = StateGraph(State)
        llm_with_tools = llm.bind_tools(tools)

        def chatbot(state: State):
            return {"messages": [llm_with_tools.invoke(state["messages"])]}

        graph_builder.add_node("chatbot", chatbot)
        graph_builder.add_node("tools", ToolNode(tools=tools))
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        graph_builder.set_entry_point("chatbot")

        if memory is None:
            memory = MemorySaver()

        self.graph = graph_builder.compile(checkpointer=memory)
        self.memory = memory

    
    async def _connect_to_server(self, server_name, server_config):
        server_params = StdioServerParameters(**server_config)
        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        mcp_tools = await load_mcp_tools(session)
        self.sessions_to_tools[session] = mcp_tools
        self.tools.extend(mcp_tools)


    async def initialize_mcp_connection(self):
        if self._is_connected:
            print("[INFO] Initialize MCP Connection called, but agent MCP services are already initialized")
            return

        self.exit_stack = AsyncExitStack()
        await self.exit_stack.__aenter__()    # TODO: Check if neccesary

        with open(server_config_path, "r") as file:
            data = json.load(file)
        servers = data.get("mcpServers", {})
        
        for server_name, server_config in servers.items():
            await self._connect_to_server(server_name, server_config)

        self._is_connected = True

    async def setup_mcp(self):
        self.tools = local_tools

        await self.initialize_mcp_connection()

        self._create_langgraph_agent(self.model_enum, self.tools, memory=self.memory)
    
    async def ainvoke(self, **kwargs):
        if not self._is_connected:
            await self.setup_mcp()

        result = await self.graph.ainvoke(**kwargs)
        return result

    async def aclose(self):
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.exit_stack = None
        self._is_connected = False

    def invoke(self, **kwargs):
        async def _wrapped():
            try:
                return await self.ainvoke(**kwargs)
            finally:
                await self.aclose()
        return asyncio.run(_wrapped())
