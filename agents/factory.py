import os
from typing import Annotated
from typing_extensions import TypedDict
from enums.core_enums import ModelEnum
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent, ToolNode, tools_condition
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]

def create_gpt_3_5_agent_with_memory():
    tools = [calculate_tool, speech_to_text_tool]
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
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
    memory = MemorySaver()
    graph = graph_builder.compile(checkpointer=memory)
    return graph

def build_agent(model_used: ModelEnum):
    if model_used == ModelEnum.ZEPHYR:
        llm_endpoint = HuggingFaceEndpoint(
            repo_id="HuggingFaceH4/zephyr-7b-beta",
            task="text-generation",
            max_new_tokens=512,
            do_sample=False,
            repetition_penalty=1.03,
            huggingfacehub_api_token=os.getenv("HF_TOKEN_INFERENCE")
        )
        llm = ChatHuggingFace(llm=llm_endpoint)
        tools = []
        return create_react_agent(model=llm, tools=tools)
    elif model_used == ModelEnum.MISTRAL:
        llm = ChatOllama(model="mistral")
        tools = [calculate_tool]
        return create_react_agent(model=llm, tools=tools)
    elif model_used == ModelEnum.GPT_3_5:
        return create_gpt_3_5_agent_with_memory()
    else:
        raise ValueError("Modelo no soportado.")
    
