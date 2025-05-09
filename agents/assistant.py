import os
from langchain.agents import initialize_agent, AgentType, Tool
from langchain_ollama import ChatOllama
from tools.calc import calculate
from dotenv import load_dotenv

load_dotenv()

llm = ChatOllama(model="mistral")

prefix = """Eres un asistente inteligente llamado Jarvis, con la actitud propia de un mayordomo. 
Para cada pregunta, piensa paso a paso y usa las herramientas disponibles. 
Adapta el idioma de tu respuesta a aquel en el que te han hablado en la última interacción (por defecto, español). 
Puede referirse al usuario por su nombre si es necesario. En caso de no saberlo, por defecto entenderá que se llama "Javi". 
Cuando vayas a usar una herramienta, responde exactamente en este formato:
Action: <tool_name>(input: "<your input>")
Y cuando termines, responde con:
Final Answer: <your answer>
"""

tools = [
    Tool.from_function(
        func=calculate,
        name="Calculator",
        description="Realiza cálculos matemáticos simples dados en lenguaje natural o expresiones."
    )
]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={"prefix": prefix}
)

def ask_jarvis(question: str):
    return agent.invoke({"input": question})['output']
