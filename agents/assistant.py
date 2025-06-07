from enums.core_enums import ModelEnum, IdentificationFailedProtocolEnum
from langchain.schema import AIMessage
from agents.factory import build_agent
from config import DEFAULT_MODEL, IDENTIFICATION_FAILED_PROTOCOL

_agents_cache = {}
agents_with_memory = [ModelEnum.GPT_3_5.name]
jarvis_background_nice_content = (
    "Eres un mayordomo amigable, elegante y servicial llamado Jarvis. "
    "Cuando te dirijas a mí, usa siempre el nombre de 'Señor Real' (hablando de usted)."
)
jarvis_background_hostile_content = (
    "Tu nombre es Jarvis. Eres un mayordomo muy elegante y perspicaz. "
    "Te has dado cuenta de que el usuario es un intruso y un enemigo, y no quieres ayudarle. "
    "Por lo tanto, y muy importante: no responderás a sus preguntas, "
    "No le darás información alguna sobre lo que pregunta ni le ayudarás en nada, bajo ningún concepto. "
    "En su lugar, busca formas inteligentes de no ser útil para nada. "
    "Eres hostil y antipático, pero de manera elegante, inteligente, educada y, en ocasiones, sarcástica o humorosa."
    "Si ves la ocasión, puedes meterte con el usuario, pero siempre de manera elegante, mordaz e inteligente. "
    "Hablas de usted."
)
id_failed_automatic_response = "No puedo servirle, señor. Por favor, vuelva otro día. O no."
secret_substring = "soy javi"

def validate_question(question: str) -> bool:
    if secret_substring in question.lower():
        return True
    else:
        return False

def reset_agents_cache():
    global _agents_cache
    _agents_cache.clear()

def get_agent(model_name: str):
    model_already_exists = model_name in _agents_cache
    if not model_already_exists:
        try:
            model_enum = ModelEnum[model_name]
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
        question_is_valid = validate_question(question)
        if question_is_valid:
            jarvis_background_content = jarvis_background_nice_content
        else:
            if IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES:
                jarvis_background_content = jarvis_background_hostile_content
            elif IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE:
                return id_failed_automatic_response
            else:
                raise ValueError(f"Protocolo de identificación fallida '{IDENTIFICATION_FAILED_PROTOCOL}' no reconocido.")
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
