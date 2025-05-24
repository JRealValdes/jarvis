from enums.core_enums import ModelEnums
from langchain.schema import AIMessage
from agents.factory import build_agent
from config import DEFAULT_MODEL

def ask_jarvis(question: str, model_name: str = DEFAULT_MODEL.name):
    try:
        model_enum = ModelEnums[model_name]
    except KeyError:
        return f"Modelo '{model_name}' no reconocido."

    agent = build_agent(model_enum)
    response = agent.invoke({"messages": [{"role": "user", "content": question}]})
    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."
