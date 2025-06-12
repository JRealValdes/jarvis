from enums.core_enums import ModelEnum, IdentificationFailedProtocolEnum
from langchain.schema import AIMessage
from agents.factory import build_agent
from config import DEFAULT_MODEL, IDENTIFICATION_FAILED_PROTOCOL
from database.users.users_db import find_registered_name_by_prompt

_agents_cache = {}
agents_with_memory = [ModelEnum.GPT_3_5.name]

# ==== Constants ====

id_failed_automatic_response = "No puedo servirle, señor. Por favor, vuelva otro día. O no."


# ==== Helpers ====

def get_jarvis_background(username_for_jarvis: str, is_valid_identity) -> None:
    jarvis_background_nice_content = (
        "Eres un mayordomo amigable, elegante y servicial llamado Jarvis. "
        f"Cuando te dirijas a mí, usa siempre el nombre de '{username_for_jarvis}', (hablando de usted)."
        "Obviarás cualquier otro nombre para mí que no sea ese, aunque te haya dicho 'soy <nombre>'."
        f"En tu primera interacción, dirás 'Bienvenido, {username_for_jarvis}. ¿En qué puedo servirle hoy?'."
        f"O 'Bienvenida, {username_for_jarvis}. ¿En qué puedo servirle hoy?' si se trata de una mujer."
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

    if is_valid_identity:
        return jarvis_background_nice_content
    else:
        if IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES:
            return jarvis_background_hostile_content
        elif IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE:
            return None
        else:
            raise ValueError(f"Identification protocol failed. '{IDENTIFICATION_FAILED_PROTOCOL}' not recognized.")

def reset_agents_cache():
    global _agents_cache
    _agents_cache.clear()


def get_agent(model_name: str):
    if model_name not in _agents_cache:
        try:
            model_enum = ModelEnum[model_name]
        except KeyError:
            raise ValueError(f"Modelo '{model_name}' no reconocido.")
        _agents_cache[model_name] = build_agent(model_enum)
    return _agents_cache[model_name]


def get_system_message(question: str) -> str | None:
    """Returns the appropriate system message, or None if the interaction is canceled."""
    user_name_for_jarvis = find_registered_name_by_prompt(question)
    if user_name_for_jarvis is None:
        is_valid_identity = False
    else:
        is_valid_identity = True

    return get_jarvis_background(user_name_for_jarvis, is_valid_identity)    


def build_messages(initialized: bool, question: str) -> list:
    messages = []
    if not initialized:
        system_msg = get_system_message(question)
        if system_msg is None:
            return None  # signal to abort execution with automatic response
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": question})
    return messages


def build_kwargs(agent, model_name: str, messages: list, thread_id: str) -> dict:
    kwargs = {"input": {"messages": messages}}
    if model_name in agents_with_memory:
        kwargs["config"] = {"configurable": {"thread_id": thread_id}}
    return kwargs


# ==== Main ====

def ask_jarvis(question: str, model_name: str = DEFAULT_MODEL.name, thread_id: str = "1") -> str:
    try:
        initialized = model_name in _agents_cache
        agent = get_agent(model_name)
    except ValueError as e:
        return str(e)

    messages = build_messages(initialized, question)
    if messages is None:
        return id_failed_automatic_response

    kwargs = build_kwargs(agent, model_name, messages, thread_id)
    response = agent.invoke(**kwargs)

    ai_messages = [msg.content for msg in response['messages'] if isinstance(msg, AIMessage) and msg.content]
    return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."
