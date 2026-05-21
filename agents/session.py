"""Orquestación de sesiones de chat, caché de agentes e invocación del LLM."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.factory import build_agent, models_with_memory
from config import DEFAULT_MODEL, IDENTIFICATION_FAILED_PROTOCOL
from domain.chat.chat_state import (
    ChatState,
    compute_next_chat_state,
    should_clear_agent_thread_on_identification,
)
from domain.users.identification import find_user_by_prompt
from domain.users.prompts import (
    AUTOMATIC_RESPONSE_IF_ID_FAILED,
    build_background_prompt,
    get_welcome_message,
)
from enums.core_enums import ModelEnum

not_verbosed_tools = ["get_upcoming_events_tool"]

_sessions_cache: dict[tuple[ModelEnum, str], "JarvisSession"] = {}
_agents_cache: dict[ModelEnum, object] = {}


def get_cache_status() -> dict:
    """
    Resume el estado de las cachés globales de agentes y sesiones.

    Returns:
        Dict con claves ``agents_cache_count``, ``sessions_cache_count``,
        ``agent_models`` (nombres) y ``sessions`` (pares modelo/hilo).
    """
    sessions = [(key[0].name, key[1]) for key in _sessions_cache.keys()]
    return {
        "agents_cache_count": len(_agents_cache),
        "sessions_cache_count": len(_sessions_cache),
        "agent_models": [model.name for model in _agents_cache.keys()],
        "sessions": list(map(str, sessions)),
    }


def check_individual_session_cache_exists(
    thread_id: str, model: ModelEnum = DEFAULT_MODEL
) -> bool:
    """
    Indica si existe una sesión en caché para el hilo y modelo dados.

    Args:
        thread_id: Identificador de conversación (p. ej. real_name del usuario).
        model: Modelo asociado a la sesión.

    Returns:
        True si la clave (model, thread_id) está en caché.
    """
    return (model, thread_id) in _sessions_cache


def ask_jarvis(
    prompt: str,
    model: ModelEnum = DEFAULT_MODEL,
    thread_id: str = "1",
    user_info: dict | None = None,
) -> list[str]:
    """
    Punto de entrada principal para enviar un mensaje a Jarvis.

    Args:
        prompt: Mensaje del usuario.
        model: Modelo LLM a usar.
        thread_id: Identificador de hilo / sesión.
        user_info: Dict de usuario autenticado (API); None en CLI sin JWT.

    Returns:
        Lista de fragmentos de respuesta (texto) para mostrar al usuario.
    """
    session_key = (model, thread_id)
    if session_key not in _sessions_cache:
        _sessions_cache[session_key] = JarvisSession(model, thread_id, user_info)
    result = _sessions_cache[session_key].ask(prompt)

    if isinstance(result, list):
        return result
    return [result]


def reset_session(thread_id: str, model: ModelEnum = DEFAULT_MODEL) -> None:
    """
    Elimina la sesión en caché y el hilo de memoria del agente si aplica.

    Args:
        thread_id: Hilo a limpiar.
        model: Modelo asociado al hilo.

    Returns:
        None.
    """
    session_key = (model, thread_id)
    agent = _agents_cache.get(model)
    if agent and hasattr(agent, "memory") and agent.memory:
        agent.memory.delete_thread(thread_id)
    _sessions_cache.pop(session_key, None)


def reset_cache_global() -> None:
    """
    Vacía por completo las cachés de agentes y sesiones.

    Returns:
        None.
    """
    global _agents_cache, _sessions_cache
    _agents_cache.clear()
    _sessions_cache.clear()


reset_cache = reset_cache_global
"""Alias usado por la UI Gradio (``app.py``)."""


def _parse_message_list(messages: list) -> list[dict]:
    """
    Convierte mensajes LangChain a dicts ``{role, content}`` para la API.

    Args:
        messages: Lista de SystemMessage, HumanMessage, AIMessage, ToolMessage.

    Returns:
        Lista de dicts con roles ``system``, ``user`` o ``assistant``.
    """
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            if "tool_calls" in msg.additional_kwargs:
                for tool_call in msg.additional_kwargs["tool_calls"]:
                    args_dict = json.loads(tool_call["function"]["arguments"])
                    args_str = ", ".join(f"{key}={value}" for key, value in args_dict.items())
                    if args_str:
                        result.append({
                            "role": "assistant",
                            "content": (
                                f"Llamando a la función: {tool_call['function']['name']}. "
                                f"Argumentos: {args_str}"
                            ),
                        })
                    else:
                        result.append({
                            "role": "assistant",
                            "content": (
                                f"Llamando a la función: {tool_call['function']['name']}. "
                                "Sin argumentos."
                            ),
                        })
            else:
                result.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            if msg.name not in not_verbosed_tools or "error" in msg.content.lower():
                result.append({
                    "role": "assistant",
                    "content": f"Resultado de la función {msg.name}: {msg.content}",
                })
    return result


def get_message_history(thread_id: str, model: ModelEnum = DEFAULT_MODEL) -> list[dict]:
    """
    Obtiene el historial parseado de un hilo si la sesión está en caché.

    Args:
        thread_id: Identificador de conversación.
        model: Modelo del agente en caché.

    Returns:
        Lista de mensajes ``{role, content}``; lista vacía si no hay sesión o falla.
    """
    print(f"Sessions cache: {_sessions_cache}")
    session_key = (model, thread_id)
    if session_key not in _sessions_cache:
        print(f"[Warning] No session found for thread {thread_id} with model {model.name}.")
        return []
    try:
        agent = _sessions_cache[session_key].agent
        last_snapshot = list(
            agent.graph.get_state_history({"configurable": {"thread_id": thread_id}})
        )[0]
        messages = last_snapshot.values.get("messages", [])
        return _parse_message_list(messages)
    except Exception as e:
        print(f"[Error] Failed to retrieve message history for thread {thread_id}: {e}")
        return []


class JarvisSession:
    """
    Orquesta un turno de conversación: estado, prompts y agente LLM.

    Attributes:
        model_enum: Modelo LLM de la sesión.
        thread_id: Identificador de hilo.
        valid_user: Si hay usuario identificado o autenticado.
        user: Dict con datos de usuario (real_name, jarvis_name, etc.).
        agent: Instancia de agente desde caché global.
    """

    def __init__(
        self,
        model_enum: ModelEnum = DEFAULT_MODEL,
        thread_id: str = "1",
        user_info: dict | None = None,
    ) -> None:
        """
        Args:
            model_enum: Modelo a usar.
            thread_id: Hilo de conversación.
            user_info: Usuario autenticado vía API; None si no hay JWT.
        """
        self.model_enum = model_enum
        self.thread_id = thread_id
        self.valid_user = bool(user_info)
        self.user = user_info
        self.agent = self._load_or_build_agent()
        self._chat_state = ChatState.NOT_INITIALIZED

    def _load_or_build_agent(self) -> object:
        """
        Obtiene el agente desde caché global o lo construye.

        Returns:
            Instancia de agente (Basic, Memory o MCP).
        """
        if self.model_enum not in _agents_cache:
            _agents_cache[self.model_enum] = build_agent(self.model_enum)
        return _agents_cache[self.model_enum]

    def _try_identify_user(self, prompt: str) -> None:
        """
        Intenta identificar al usuario por patrón en el prompt.

        Args:
            prompt: Mensaje del usuario.

        Returns:
            None. Actualiza ``valid_user`` y ``user`` si hay match.
        """
        user = find_user_by_prompt(prompt)
        if user:
            self.valid_user = True
            self.user = user

    def _update_chat_state(self, prompt: str) -> None:
        """
        Avanza la máquina de estados y aplica efectos de memoria si aplica.

        Args:
            prompt: Último mensaje del usuario.

        Returns:
            None.
        """
        was_previously_invalid = not self.valid_user
        if was_previously_invalid:
            self._try_identify_user(prompt)

        previous_state = self._chat_state
        if should_clear_agent_thread_on_identification(
            previous_state,
            was_previously_invalid=was_previously_invalid,
            valid_user=self.valid_user,
        ):
            if self.agent.memory:
                self.agent.memory.delete_thread(self.thread_id)

        self._chat_state = compute_next_chat_state(
            previous_state,
            valid_user=self.valid_user,
            was_previously_invalid=was_previously_invalid,
            identification_protocol=IDENTIFICATION_FAILED_PROTOCOL,
        )

    def _build_agent_kwargs(self, messages: list) -> dict:
        """
        Construye kwargs para ``agent.invoke``.

        Args:
            messages: Lista de mensajes LangChain.

        Returns:
            Dict con ``input`` y opcionalmente ``config`` (thread_id).
        """
        real_name = self.user["real_name"] if self.user else ""
        kwargs = {"input": {"messages": messages, "real_name": real_name}}
        if self.model_enum in models_with_memory:
            kwargs["config"] = {"configurable": {"thread_id": self.thread_id}}
        return kwargs

    def _process_messages(self, messages: list) -> list[str] | str:
        """
        Invoca el agente y extrae respuestas de asistente desde el estado.

        Args:
            messages: Mensajes a enviar al grafo.

        Returns:
            Lista de cadenas de respuesta, o mensaje de error como str/lista.
        """
        try:
            kwargs = self._build_agent_kwargs(messages)
            response = self.agent.invoke(**kwargs)
            response_messages = response.get("messages", [])
            last_human_index = max(
                (i for i, msg in enumerate(response_messages) if isinstance(msg, HumanMessage)),
                default=-1,
            )
            msg_dict_list = _parse_message_list(response_messages[last_human_index + 1 :])
            result = [msg["content"] for msg in msg_dict_list]
            return result if result else "Lo siento, señor. No tengo respuesta para su petición."
        except Exception as e:
            return f"Ha habido un error procesando su petición, señor. Error: {e}"

    def ask(self, prompt: str) -> list[str] | str:
        """
        Procesa un turno de usuario y devuelve la respuesta de Jarvis.

        Args:
            prompt: Mensaje del usuario.

        Returns:
            Lista de strings (respuestas) o mensaje único según el estado.
        """
        self._update_chat_state(prompt)

        if self._chat_state == ChatState.NOT_INITIALIZED:
            return [AUTOMATIC_RESPONSE_IF_ID_FAILED]

        if self._chat_state == ChatState.JARVIS_WELCOME_MESSAGE:
            return [get_welcome_message(self.user)]

        if self._chat_state == ChatState.STARTING_CHAT:
            messages = [
                SystemMessage(content=build_background_prompt(self.valid_user, self.user))
            ]
            if self.valid_user:
                messages.append(AIMessage(content=get_welcome_message(self.user)))
            messages.append(HumanMessage(content=prompt))
            return self._process_messages(messages)

        if self._chat_state == ChatState.INITIALIZED:
            messages = [HumanMessage(content=prompt)]
            return self._process_messages(messages)
