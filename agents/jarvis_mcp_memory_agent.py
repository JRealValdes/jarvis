import os
from contextlib import AsyncExitStack
from typing import Annotated
from typing_extensions import TypedDict
from enums.core_enums import ModelEnum
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent, ToolNode, tools_condition
from langgraph.graph.message import add_messages
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool

local_tools = [calculate_tool, speech_to_text_tool]

