import os
from enums.core_enums import ModelEnums
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from tools.calc import calculate
from langgraph.prebuilt import create_react_agent

def build_agent(model_used: ModelEnums):
    if model_used == ModelEnums.ZEPHYR:
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
    elif model_used == ModelEnums.MISTRAL:
        llm = ChatOllama(model="mistral")
        tools = [calculate]
    elif model_used == ModelEnums.GPT_3_5:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        tools = [calculate]
    else:
        raise ValueError("Modelo no soportado.")
    
    return create_react_agent(model=llm, tools=tools)
