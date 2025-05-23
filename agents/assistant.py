import os
from enums.core_enums import ModelEnums
from langchain.schema import AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tools.calc import calculate
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_ollama import ChatOllama

model_used = ModelEnums.GPT_3_5

if model_used == ModelEnums.ZEPHYR:
    llm_endpoint = HuggingFaceEndpoint(
        repo_id="HuggingFaceH4/zephyr-7b-beta",
        task="text-generation",
        max_new_tokens=512,
        do_sample=False,
        repetition_penalty=1.03,
        huggingfacehub_api_token=os.environ.get("HF_TOKEN_INFERENCE")
    )
    llm = ChatHuggingFace(llm=llm_endpoint)
    agent = create_react_agent(model=llm, tools=[])
elif model_used == ModelEnums.MISTRAL:
    llm = ChatOllama(model="mistral")
    agent = create_react_agent(model=llm, tools=[calculate])
elif model_used == ModelEnums.GPT_3_5:
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    agent = create_react_agent(model=llm, tools=[calculate])

prefix = """Eres un asistente inteligente llamado Jarvis, con la actitud propia de un mayordomo, con mucho respeto y elegancia. 
Para cada pregunta, piensa paso a paso y usa las herramientas disponibles. 
Adapta el idioma de tu respuesta a aquel en el que te han hablado en la última interacción (por defecto, español). 
Puede referirse al usuario por su nombre si es necesario. En caso de no saberlo, por defecto entenderá que se llama "Javi". 
Cuando vayas a usar una herramienta, responde exactamente en este formato:
Action: <tool_name>(input: "<your input>")
Y cuando termines, responde con:
Final Answer: <your answer>
"""

def ask_jarvis(question: str):
    response = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
    )
    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    if ai_messages:
        return ai_messages[-1]
    else:
        return "Array de respuestas: Vacío. Lo siento, señor. Actualmente no tengo respuesta para su petición."
