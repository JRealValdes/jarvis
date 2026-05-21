"""Shared enumerations for the Jarvis domain."""

from enum import Enum


class ModelEnum(Enum):
    """Language models supported by the agent factory."""

    GPT_3_5 = "chatgpt_3_5"
    GPT_4 = "chatgpt_4"
    ZEPHYR = "zephyr"
    MISTRAL = "mistral"


class IdentificationFailedProtocolEnum(Enum):
    """Protocol when user identification fails in CLI/UI session."""

    HOSTILE_RESPONSES = "hostile_responses"
    AUTOMATIC_RESPONSE = "automatic_response"
