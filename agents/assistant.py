from enums.core_enums import ModelEnums
from langchain.schema import AIMessage
from agents.factory import build_agent
from config import DEFAULT_MODEL

_agents_cache = {}
agents_with_memory = [ModelEnums.GPT_3_5.name]

def reset_agents_cache():
    global _agents_cache
    _agents_cache.clear()

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

    kwargs_model_invocation = {"input": {"messages": [{"role": "user", "content": question}]}}
    if model_name in agents_with_memory:
        kwargs_model_invocation["config"] = {"configurable": {"thread_id": "1"}}

    response = agent.invoke(**kwargs_model_invocation)

    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."
