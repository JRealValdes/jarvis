"""Enumeraciones compartidas del dominio Jarvis."""

from enum import Enum


class ModelEnum(Enum):
    """Modelos de lenguaje soportados por la factoría de agentes."""

    GPT_3_5 = "chatgpt_3_5"
    GPT_4 = "chatgpt_4"
    ZEPHYR = "zephyr"
    MISTRAL = "mistral"


class IdentificationFailedProtocolEnum(Enum):
    """Protocolo cuando falla la identificación del usuario en sesión CLI/UI."""

    HOSTILE_RESPONSES = "hostile_responses"
    AUTOMATIC_RESPONSE = "automatic_response"
