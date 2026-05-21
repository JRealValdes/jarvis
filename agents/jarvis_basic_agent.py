"""ReAct agent without persistent memory (Zephyr via HF, Mistral via Ollama)."""

import os

from core.enums import ModelEnum
from langchain_ollama import ChatOllama
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langgraph.prebuilt import create_react_agent
from tools.tools_registry import local_tools


class JarvisBasicAgent:
    """
    Prebuilt LangGraph ReAct agent for local or HuggingFace models.

    Attributes:
        model_enum: Configured model.
        graph: Compiled invocable graph.
        memory: Always None for this agent.
        tools: Registered LangChain tools list.
    """

    def __init__(self, model_enum: ModelEnum) -> None:
        """
        Args:
            model_enum: ZEPHYR or MISTRAL.

        Raises:
            ValueError: If the model is not supported by this class.
        """
        self.model_enum = model_enum
        self.graph, self.memory, self.tools = self._build_agent(model_enum)

    def _build_agent(
        self, model_enum: ModelEnum
    ) -> tuple[object, None, list]:
        """
        Build the ReAct graph and associated tools.

        Args:
            model_enum: Model to instantiate.

        Returns:
            Tuple (graph, memory, tools) with memory=None.

        Raises:
            ValueError: If model_enum is neither ZEPHYR nor MISTRAL.
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
        Run a graph invocation.

        Args:
            **kwargs: Arguments accepted by ``graph.invoke`` (input, config, etc.).

        Returns:
            Resulting graph state (dict with keys such as ``messages``).
        """
        return self.graph.invoke(**kwargs)

    def cleanup(self) -> None:
        """Release agent resources (no-op for this agent)."""
        pass
