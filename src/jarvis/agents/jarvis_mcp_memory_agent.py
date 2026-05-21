"""GPT-3.5 agent with memory, local tools, and MCP servers via stdio."""

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack

logger = logging.getLogger(__name__)
from typing import Annotated

from typing_extensions import TypedDict

from core.enums import ModelEnum
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tools.tools_registry import local_tools


class State(TypedDict):
    """Graph state with messages and real_name injected into tools."""

    messages: Annotated[list, add_messages]
    real_name: str


from core.paths import MCP_SERVER_CONFIG_PATH

server_config_path = str(MCP_SERVER_CONFIG_PATH)


class JarvisMcpMemoryAgent:
    """
    Agent with memory combining local tools and MCP server tools.

    MCP connection is established lazily on the first invocation.
    """

    def __init__(self, model_enum: ModelEnum) -> None:
        """
        Args:
            model_enum: Must be GPT_3_5.
        """
        self.model_enum = model_enum
        self.exit_stack: AsyncExitStack | None = None
        self.tools: list | None = None
        self.graph = None
        self.memory: MemorySaver | None = None
        self._is_connected = False

    def _create_langgraph_agent(
        self, model_enum: ModelEnum, tools: list, memory: MemorySaver | None = None
    ) -> None:
        """
        Compile the LangGraph with the given tools.

        Args:
            model_enum: LLM model (GPT_3_5).
            tools: Local + MCP tools.
            memory: Checkpointer; MemorySaver is created if None.

        Raises:
            ValueError: If the model is not GPT_3_5.
        """
        if model_enum == ModelEnum.GPT_3_5:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        else:
            raise ValueError(f"Unsupported model: {model_enum}")

        graph_builder = StateGraph(State)
        llm_with_tools = llm.bind_tools(tools)

        def chatbot(state: State) -> dict:
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

    async def _connect_to_server(self, server_name: str, server_config: dict) -> None:
        """
        Connect to an MCP server over stdio and append its tools.

        Args:
            server_name: Logical server name (for logging).
            server_config: Parameters for StdioServerParameters.
        """
        server_params = StdioServerParameters(**server_config)
        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        mcp_tools = await load_mcp_tools(session)
        self.tools.extend(mcp_tools)

    async def initialize_mcp_connection(self) -> None:
        """
        Read ``mcp/server_config.json`` and connect all MCP servers.

        Returns:
            None. Idempotent if already connected.
        """
        if self._is_connected:
            logger.info(
                "Initialize MCP Connection called, but MCP services are already initialized"
            )
            return

        self.exit_stack = AsyncExitStack()
        await self.exit_stack.__aenter__()

        with open(server_config_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        servers = data.get("mcpServers", {})

        for server_name, server_config in servers.items():
            await self._connect_to_server(server_name, server_config)

        self._is_connected = True

    async def setup_mcp(self) -> None:
        """
        Initialize local tools, MCP connection, and LangGraph.

        Returns:
            None.
        """
        self.tools = list(local_tools)
        await self.initialize_mcp_connection()
        self._create_langgraph_agent(self.model_enum, self.tools, memory=self.memory)

    async def ainvoke(self, **kwargs) -> dict:
        """
        Async graph invocation (connects MCP if needed).

        Args:
            **kwargs: Arguments for ``graph.ainvoke``.

        Returns:
            Final graph state.
        """
        if not self._is_connected:
            await self.setup_mcp()
        return await self.graph.ainvoke(**kwargs)

    async def aclose(self) -> None:
        """
        Close MCP sessions and reset the connection flag.

        Returns:
            None.
        """
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.exit_stack = None
        self._is_connected = False

    def invoke(self, **kwargs) -> dict:
        """
        Synchronous wrapper that runs ainvoke and closes MCP when done.

        Args:
            **kwargs: Arguments for ``ainvoke``.

        Returns:
            Final graph state.
        """

        async def _wrapped() -> dict:
            try:
                return await self.ainvoke(**kwargs)
            finally:
                await self.aclose()

        return asyncio.run(_wrapped())
