from enums.core_enums import ModelEnums
from langchain.schema import AIMessage
from agents.factory import build_agent
from config import DEFAULT_MODEL

_agents_cache = {}
agents_with_memory = [ModelEnums.GPT_3_5.name]
jarvis_background_content = (
    "Eres un mayordomo amigable, elegante y servicial llamado Jarvis. "
    "Cuando te dirijas a mí, usa siempre el nombre de 'Señor Real'."
)

def reset_agents_cache():
    global _agents_cache
    _agents_cache.clear()

def get_agent(model_name: str):
    model_already_exists = model_name in _agents_cache
    if not model_already_exists:
        try:
            model_enum = ModelEnums[model_name]
        except KeyError:
            raise ValueError(f"Modelo '{model_name}' no reconocido.")
        agent = build_agent(model_enum)
        _agents_cache[model_name] = agent
    return _agents_cache[model_name], model_already_exists

def ask_jarvis(question: str, model_name: str = DEFAULT_MODEL.name, thread_id: str = "1") -> str:
    try:
        agent, model_already_exists = get_agent(model_name)
    except ValueError as e:
        return str(e)

    if not model_already_exists:
        messages = [
            {
                "role": "system",
                "content": jarvis_background_content
            }
        ]
    else:
        messages = []
    
    messages.append({"role": "user", "content": question})

    kwargs_model_invocation = {"input": {"messages": messages}}
    if model_name in agents_with_memory:
        kwargs_model_invocation["config"] = {"configurable": {"thread_id": thread_id}}

    response = agent.invoke(**kwargs_model_invocation)

    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."
