from enum import Enum

class ModelEnum(Enum):
    GPT_3_5 = "chatgpt_3_5"
    GPT_4 = "chatgpt_4"
    ZEPHYR = "zephyr"
    MISTRAL = "mistral"

class IdentificationFailedProtocolEnum(Enum):
    HOSTILE_RESPONSES = "hostile_responses"
    AUTOMATIC_RESPONSE = "automatic_response"
