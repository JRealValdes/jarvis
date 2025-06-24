import os
from enums.core_enums import ModelEnum
from langchain_ollama import ChatOllama
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.prebuilt import create_react_agent
from tools.calc import calculate_tool
from tools.speech_to_text import speech_to_text_tool

local_tools = [calculate_tool, speech_to_text_tool]

class JarvisBasicAgent:
    def __init__(self, model_enum: ModelEnum):
        self.model_enum = model_enum
        self.graph, self.memory, self.tools = self._build_agent(model_enum)

    def _build_agent(self, model_enum: ModelEnum):
        tools = local_tools
        if model_enum == ModelEnum.ZEPHYR:
            llm_endpoint = HuggingFaceEndpoint(
                repo_id="HuggingFaceH4/zephyr-7b-beta",
                task="text-generation",
                max_new_tokens=512,
                do_sample=False,
                repetition_penalty=1.03,
                huggingfacehub_api_token=os.getenv("HF_TOKEN_INFERENCE")
            )
            llm = ChatHuggingFace(llm=llm_endpoint)
        elif model_enum == ModelEnum.MISTRAL:
            llm = ChatOllama(model="mistral")
        else:
            raise ValueError("Modelo no soportado.")
        return create_react_agent(model=llm, tools=tools)

    def invoke(self, **kwargs) -> str:
        return self.graph.invoke(**kwargs)

    def cleanup(self):
        pass
