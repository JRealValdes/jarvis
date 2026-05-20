"""Agente GPT-3.5 con memoria y herramientas locales + servidores MCP vía stdio."""

import asyncio
import json
import os
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
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tools.tools_registry import local_tools


class State(TypedDict):
    """Estado del grafo con mensajes y real_name inyectado en tools."""

    messages: Annotated[list, add_messages]
    real_name: str


server_config_path = os.path.join("mcp", "server_config.json")


class JarvisMcpMemoryAgent:
    """
    Agente con memoria que combina tools locales y tools de servidores MCP.

    La conexión MCP se establece de forma lazy en la primera invocación.
    """

    def __init__(self, model_enum: ModelEnum) -> None:
        """
        Args:
            model_enum: Debe ser GPT_3_5.
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
        Compila el grafo LangGraph con las herramientas dadas.

        Args:
            model_enum: Modelo LLM (GPT_3_5).
            tools: Herramientas locales + MCP.
            memory: Checkpointer; si es None se crea MemorySaver.

        Raises:
            ValueError: Si el modelo no es GPT_3_5.
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
        Conecta a un servidor MCP por stdio y añade sus tools.

        Args:
            server_name: Nombre lógico del servidor (logging).
            server_config: Parámetros para StdioServerParameters.
        """
        server_params = StdioServerParameters(**server_config)
        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        mcp_tools = await load_mcp_tools(session)
        self.tools.extend(mcp_tools)

    async def initialize_mcp_connection(self) -> None:
        """
        Lee ``mcp/server_config.json`` y conecta todos los servidores MCP.

        Returns:
            None. Idempotente si ya estaba conectado.
        """
        if self._is_connected:
            print("[INFO] Initialize MCP Connection called, but agent MCP services are already initialized")
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
        Inicializa tools locales, conexión MCP y grafo LangGraph.

        Returns:
            None.
        """
        self.tools = list(local_tools)
        await self.initialize_mcp_connection()
        self._create_langgraph_agent(self.model_enum, self.tools, memory=self.memory)

    async def ainvoke(self, **kwargs) -> dict:
        """
        Invocación asíncrona del grafo (conecta MCP si hace falta).

        Args:
            **kwargs: Argumentos de ``graph.ainvoke``.

        Returns:
            Estado final del grafo.
        """
        if not self._is_connected:
            await self.setup_mcp()
        return await self.graph.ainvoke(**kwargs)

    async def aclose(self) -> None:
        """
        Cierra sesiones MCP y resetea el flag de conexión.

        Returns:
            None.
        """
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.exit_stack = None
        self._is_connected = False

    def invoke(self, **kwargs) -> dict:
        """
        Envoltorio síncrono que ejecuta ainvoke y cierra MCP al terminar.

        Args:
            **kwargs: Argumentos de ``ainvoke``.

        Returns:
            Estado final del grafo.
        """

        async def _wrapped() -> dict:
            try:
                return await self.ainvoke(**kwargs)
            finally:
                await self.aclose()

        return asyncio.run(_wrapped())
