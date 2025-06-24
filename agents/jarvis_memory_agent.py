from typing import Annotated
from typing_extensions import TypedDict
from enums.core_enums import ModelEnum
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool

local_tools = [calculate_tool, speech_to_text_tool]

class State(TypedDict):
    messages: Annotated[list, add_messages]

class JarvisMemoryAgent:
    def __init__(self, model_enum: ModelEnum):
        self.model_enum = model_enum
        self.graph, self.memory, self.tools = self._build_agent(model_enum)

    def _build_agent(self, model_enum: ModelEnum):
        tools = local_tools
        if model_enum == ModelEnum.GPT_3_5:
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        else:
            raise ValueError(f"Unsupported model: {model_enum}")

        graph_builder = StateGraph(State)
        llm_with_tools = llm.bind_tools(tools)

        def chatbot(state):
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
        
        return graph, memory, tools

    def invoke(self, **kwargs) -> str:
        return self.graph.invoke(**kwargs)

    def cleanup(self):
        pass
