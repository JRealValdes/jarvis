from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.schema import AIMessage
from typing import Annotated
from typing_extensions import TypedDict

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.calc import calculate_tool

llm = ChatOllama(model="mistral")
tools = [calculate_tool]
llm_with_tools = llm.bind_tools(tools)

class State(TypedDict):
    messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)

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

config = {"configurable": {"thread_id": "1"}}

# Optional: Print graph
# print(graph.get_graph())

def ask_jarvis(question: str):
    response = graph.stream(
        {"messages": [{"role": "user", "content": question}]},
        config,
        stream_mode="values",
    )
    jarvis_response = []
    for event in response:
        for value in event.values():
            if isinstance(value[-1], AIMessage):
                jarvis_response.append(value[-1].content)
    if jarvis_response:
        return '\n'.join(jarvis_response)
    else:
        return "Array de respuestas: Vacío. Lo siento, señor. Actualmente no tengo respuesta para su petición."

while True:
    query = input("Hola, señor. ¿Con qué puedo ayudarle hoy? ")
    if query.lower() in ["salir", "exit", "quit", "q"] or ("eso es todo" in query.lower() and "jarvis" in query.lower()):
        break
    response = ask_jarvis(query)
    print("Jarvis:", response)