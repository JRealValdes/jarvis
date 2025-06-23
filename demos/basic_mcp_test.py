import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # Adjust the path to include the parent directory

from typing import Annotated
from typing_extensions import TypedDict
from enums.core_enums import ModelEnum
from langchain_openai import ChatOpenAI
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
import asyncio
from langchain_core.messages import HumanMessage
from contextlib import AsyncExitStack

local_tools = [calculate_tool, speech_to_text_tool]

models_with_memory = [ModelEnum.GPT_3_5]

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

    async def setup(self):
        server_params = StdioServerParameters(command=command, args=command_args)
        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

        mcp_tools = await load_mcp_tools(self.session)
        local_tools = [calculate_tool, speech_to_text_tool]
        self.tools = mcp_tools + local_tools
        self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        self.graph = create_react_agent(self.llm, self.tools)

    async def invoke(self, prompt: str):
        result = await self.graph.ainvoke({"messages": [HumanMessage(content=prompt)]})
        return result

    async def close(self):
        await self.exit_stack.aclose()

async def main():
    agent = AgentWithMCP()
    await agent.setup()

    try:
        result = await agent.invoke("¿Cuánto es 2+2?")
        for msg in result["messages"]:
            print("Jarvis:", msg.content)
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
