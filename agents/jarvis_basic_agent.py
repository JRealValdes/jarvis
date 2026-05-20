"""Agente ReAct sin memoria persistente (Zephyr vía HF, Mistral vía Ollama)."""

import os

from enums.core_enums import ModelEnum
from langchain_ollama import ChatOllama
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.prebuilt import create_react_agent
from tools.tools_registry import local_tools


class JarvisBasicAgent:
    """
    Agente LangGraph preconstruido (ReAct) para modelos locales o HuggingFace.

    Attributes:
        model_enum: Modelo configurado.
        graph: Grafo compilado invocable.
        memory: Siempre None en este agente.
        tools: Lista de herramientas LangChain registradas.
    """

    def __init__(self, model_enum: ModelEnum) -> None:
        """
        Args:
            model_enum: ZEPHYR o MISTRAL.

        Raises:
            ValueError: Si el modelo no está soportado en esta clase.
        """
        self.model_enum = model_enum
        self.graph, self.memory, self.tools = self._build_agent(model_enum)

    def _build_agent(
        self, model_enum: ModelEnum
    ) -> tuple[object, None, list]:
        """
        Construye el grafo ReAct y las herramientas asociadas.

        Args:
            model_enum: Modelo a instanciar.

        Returns:
            Tupla (graph, memory, tools) con memory=None.

        Raises:
            ValueError: Si model_enum no es ZEPHYR ni MISTRAL.
        """
        tools = local_tools
        if model_enum == ModelEnum.ZEPHYR:
            llm_endpoint = HuggingFaceEndpoint(
                repo_id="HuggingFaceH4/zephyr-7b-beta",
                task="text-generation",
                max_new_tokens=512,
                do_sample=False,
                repetition_penalty=1.03,
                huggingfacehub_api_token=os.getenv("HF_TOKEN_INFERENCE"),
            )
            llm = ChatHuggingFace(llm=llm_endpoint)
        elif model_enum == ModelEnum.MISTRAL:
            llm = ChatOllama(model="mistral")
        else:
            raise ValueError("Modelo no soportado.")
        graph = create_react_agent(model=llm, tools=tools)
        return graph, None, tools

    def invoke(self, **kwargs) -> dict:
        """
        Ejecuta una invocación del grafo.

        Args:
            **kwargs: Argumentos aceptados por ``graph.invoke`` (input, config, etc.).

        Returns:
            Estado resultante del grafo (dict con claves como ``messages``).
        """
        return self.graph.invoke(**kwargs)

    def cleanup(self) -> None:
        """Libera recursos del agente (no-op en este agente)."""
        pass
