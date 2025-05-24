from enums.core_enums import ModelEnums
from langchain.schema import AIMessage
from agents.factory import build_agent
from config import DEFAULT_MODEL

_agents_cache = {}

def get_agent(model_name: str):
    if model_name not in _agents_cache:
        try:
            model_enum = ModelEnums[model_name]
        except KeyError:
            raise ValueError(f"Modelo '{model_name}' no reconocido.")
        agent = build_agent(model_enum)
        _agents_cache[model_name] = agent
    return _agents_cache[model_name]

def ask_jarvis(question: str, model_name: str = DEFAULT_MODEL.name):
    try:
        agent = get_agent(model_name)
    except ValueError as e:
        return str(e)

    if model_name == ModelEnums.GPT_3_5.name:
        config = {"configurable": {"thread_id": "1"}}
        response = agent.invoke(
            input={"messages": [{"role": "user", "content": question}]},
            config=config
        )
    else:
        response = agent.invoke({"messages": [{"role": "user", "content": question}]})

    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."
