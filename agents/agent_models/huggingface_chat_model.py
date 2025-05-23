from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from huggingface_hub import InferenceClient
from typing import Any, List
from pydantic import Field
import os

class HuggingFaceChatModel(BaseChatModel):
    repo_id: str = "HuggingFaceH4/zephyr-7b-beta"
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.95
    hf_token: str = Field(default_factory=lambda: os.environ.get("HF_TOKEN_INFERENCE"))

    def _convert_messages(self, messages):
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
        return result

    def _generate(self, messages, stop=None, **kwargs) -> ChatResult:
        hf_messages = self._convert_messages(messages)

        client = InferenceClient(self.repo_id, token=self.hf_token)

        response = client.chat_completion(
            hf_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )

        text = response.choices[0].message.content
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=text))]
        )

    @property
    def _llm_type(self) -> str:
        return "huggingface-zephyr"
