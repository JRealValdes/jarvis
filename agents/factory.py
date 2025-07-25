from enums.core_enums import ModelEnum
from agents.jarvis_memory_agent import JarvisMemoryAgent
from agents.jarvis_mcp_memory_agent import JarvisMcpMemoryAgent
from agents.jarvis_basic_agent import JarvisBasicAgent

models_with_memory = [ModelEnum.GPT_3_5]

def build_agent(model_used: ModelEnum):
    if model_used in [ModelEnum.ZEPHYR, ModelEnum.MISTRAL]:
        return JarvisBasicAgent(model_used)
    elif model_used == ModelEnum.GPT_3_5:
        return JarvisMemoryAgent(model_used)
        # return JarvisMcpMemoryAgent(model_used)
    else:
        raise ValueError("Modelo no soportado.")
