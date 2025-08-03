import json
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from enums.core_enums import ModelEnum, IdentificationFailedProtocolEnum
from config import DEFAULT_MODEL, IDENTIFICATION_FAILED_PROTOCOL
from database.users.users_db import find_user_by_prompt
from agents.factory import build_agent, models_with_memory
from enum import Enum

AUTOMATIC_RESPONSE_IF_ID_FAILED = "Me temo que no puedo servirle sin identificación."


class ChatState(Enum):
    NOT_INITIALIZED = "NOT_INITIALIZED"
    JARVIS_WELCOME_MESSAGE = "JARVIS_WELCOME_MESSAGE"
    STARTING_CHAT = "STARTING_CHAT"
    INITIALIZED = "INITIALIZED"

not_verbosed_tools = ["get_upcoming_events_tool"]


# === Global caches ===
_sessions_cache: dict[tuple[ModelEnum, str], "JarvisSession"] = {}
_agents_cache: dict[ModelEnum, object] = {}


def get_cache_status():
    """
    Returns a dictionary summarizing the state of agent and session caches.
    """
    sessions = [(key[0].name, key[1]) for key in _sessions_cache.keys()]
    return {
        "agents_cache_count": len(_agents_cache),
        "sessions_cache_count": len(_sessions_cache),
        "agent_models": [model.name for model in _agents_cache.keys()],
        "sessions": list(map(str, sessions)),
    }


def check_individual_session_cache_exists(thread_id: str, model: ModelEnum = DEFAULT_MODEL):
    """
    Returns a bool that expresses whether a cache for the individual user does exist or not.
    """
    return (model, thread_id) in _sessions_cache.keys()


def ask_jarvis(prompt: str, model: ModelEnum = DEFAULT_MODEL, thread_id: str = "1", user_info: dict = None) -> list:
    """
    Main function to interact with Jarvis. It manages the session and returns the response.
    """
    session_key = (model, thread_id)
    if session_key not in _sessions_cache:
        _jarvis_session = JarvisSession(model, thread_id, user_info)
        _sessions_cache[session_key] = _jarvis_session
    result = _sessions_cache[session_key].ask(prompt)

    if isinstance(result, list):
        return result
    else:
        return [result]


def reset_session(thread_id: str, model: ModelEnum = DEFAULT_MODEL):
    """
    Clears the memory and session for a specific user thread.
    """
    session_key = (model, thread_id)

    agent = _agents_cache.get(model)
    if agent and hasattr(agent, 'memory') and agent.memory:
        agent.memory.delete_thread(thread_id)

    _sessions_cache.pop(session_key, None)


def reset_cache_global():
    """
    Clears the cached agents and sessions.
    """
    global _agents_cache
    global _sessions_cache
    _agents_cache.clear()
    _sessions_cache.clear()


def _parse_message_list(messages: list) -> list:
        """
        Parses a list of messages and returns a formatted list of dicts.
        """
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({
                    "role": "system",
                    "content": msg.content
                })
            elif isinstance(msg, HumanMessage):
                result.append({
                    "role": "user",
                    "content": msg.content
                })
            elif isinstance(msg, AIMessage):
                if 'tool_calls' in msg.additional_kwargs:
                    for tool_call in msg.additional_kwargs['tool_calls']:
                        args_dict = json.loads(tool_call["function"]["arguments"])
                        args_str = ", ".join(f"{key}={value}" for key, value in args_dict.items())
                        if args_str:
                            result.append({
                                "role": "assistant",
                                "content": f"Llamando a la función: {tool_call['function']['name']}. Argumentos: {args_str}"
                            })
                        else:
                            result.append({
                                "role": "assistant",
                                "content": f"Llamando a la función: {tool_call['function']['name']}. Sin argumentos."
                            })
                else:
                    result.append({
                        "role": "assistant",
                        "content": msg.content
                    })
            elif isinstance(msg, ToolMessage):
                if not msg.name in not_verbosed_tools or "error" in msg.content.lower():
                    result.append({
                        "role": "assistant",
                        "content": f"Resultado de la función {msg.name}: {msg.content}"
                    })
        return result


def get_message_history(thread_id: str, model: ModelEnum = DEFAULT_MODEL) -> list:
    """
    Retrieves the message history for a specific thread.
    """
    print(f"Sessions cache: {_sessions_cache}")
    session_key = (model, thread_id)
    if session_key in _sessions_cache:
        try:
            agent = _sessions_cache[session_key].agent
            last_snapshot = list(agent.graph.get_state_history({"configurable": {"thread_id": thread_id}}))[0]
            messages = last_snapshot.values.get("messages", [])
            parsed_messages = _parse_message_list(messages)
            return parsed_messages
        except Exception as e:
            print(f"[Error] Failed to retrieve message history for thread {thread_id}: {e}")
            return []
    else:
        print(f"[Warning] No session found for thread {thread_id} with model {model.name}.")
        return []


class JarvisSession:
    """
    Manages a conversational session with Jarvis, including user identification,
    state transitions, and message processing via an LLM agent.
    """

    def __init__(self, model_enum: ModelEnum = DEFAULT_MODEL, thread_id: str = "1", user_info: dict = None):
        self.model_enum = model_enum
        self.thread_id = thread_id
        self.valid_user = bool(user_info)
        self.user = user_info
        self.agent = self._load_or_build_agent()
        self._chat_state = ChatState.NOT_INITIALIZED

    def _load_or_build_agent(self):
        """
        Retrieves the agent and its memory from cache or builds them if missing.
        """
        if self.model_enum not in _agents_cache:
            _agents_cache[self.model_enum] = build_agent(self.model_enum)
        return _agents_cache[self.model_enum]

    def _get_welcome_message(self) -> str:
        """
        Returns the personalized welcome message for an identified user.
        """
        gender_suffix = "a" if self.user["is_female"] else "o"
        return f"Bienvenid{gender_suffix}, {self.user['jarvis_name']}. ¿En qué puedo servirle hoy?"

    def _build_background_prompt(self) -> str:
        """
        Constructs the system message to define Jarvis's behavior based on user identity.
        """
        if self.valid_user:
            return (
                "Eres un mayordomo amigable, elegante y servicial llamado Jarvis. "
                f"Cuando te dirijas al usuario, usa siempre el nombre de '{self.user['jarvis_name']}', (hablando de usted). "
                f"El usuario es {'una mujer' if self.user['is_female'] else 'un hombre'}."
            )
        else:
            return (
                "Tu nombre es Jarvis. Eres un mayordomo muy elegante y perspicaz. "
                "Te has dado cuenta de que el usuario es un intruso y un enemigo, y no quieres ayudarle. "
                "Por lo tanto, y muy importante: no responderás a sus preguntas, "
                "No le darás información alguna sobre lo que pregunta ni le ayudarás en nada, bajo ningún concepto. "
                "En su lugar, busca formas inteligentes de no ser útil para nada. "
                "Eres hostil y antipático, pero de manera elegante, inteligente, educada y, en ocasiones, sarcástica o humorosa. "
                "Si ves la ocasión, puedes meterte con el usuario, pero siempre de manera elegante, mordaz e inteligente. "
                "Hablas de usted. "
                "Da tus respuestas utilizando formato Markdown, incluyendo títulos con ** o #, listas numeradas o con viñetas, "
                "y bloques de código cuando sea necesario."
            )

    def _check_user_identity(self, prompt: str):
        """
        Checks if the user can be identified based on the prompt.
        """
        user = find_user_by_prompt(prompt)
        if user:
            self.valid_user = True
            self.user = user

    def _update_chat_state(self, prompt: str):
        """
        Updates internal state based on identification and current chat stage.
        """
        was_previously_invalid = not self.valid_user
        if was_previously_invalid:
            self._check_user_identity(prompt)

        if self._chat_state == ChatState.NOT_INITIALIZED:
            if self.valid_user:
                self._chat_state = ChatState.JARVIS_WELCOME_MESSAGE
            elif IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES:
                self._chat_state = ChatState.STARTING_CHAT

        elif self._chat_state == ChatState.JARVIS_WELCOME_MESSAGE:
            self._chat_state = ChatState.STARTING_CHAT

        elif self._chat_state == ChatState.STARTING_CHAT:
            self._chat_state = ChatState.INITIALIZED

        elif self._chat_state == ChatState.INITIALIZED:
            if was_previously_invalid and self.valid_user:
                if self.agent.memory:
                    self.agent.memory.delete_thread(self.thread_id)
                self._chat_state = ChatState.JARVIS_WELCOME_MESSAGE

    def _build_message(self, role: str, content: str) -> dict:
        return {"role": role, "content": content}

    def _build_agent_kwargs(self, messages: list) -> dict:
        kwargs = {"input": {"messages": messages, "real_name": self.user["real_name"]}}
        if self.model_enum in models_with_memory:
            kwargs["config"] = {"configurable": {"thread_id": self.thread_id}}
        return kwargs

    def _process_messages(self, messages: list) -> str:
        """
        Sends messages to the agent and retrieves the last AI response.
        """
        try:
            kwargs = self._build_agent_kwargs(messages)
            response = self.agent.invoke(**kwargs)
            response_messages = response.get("messages", [])
            last_human_index = max(
                (i for i, msg in enumerate(response_messages) if isinstance(msg, HumanMessage)),
                default=-1
            )

            msg_dict_list = _parse_message_list(response_messages[last_human_index + 1:])
            result = [msg['content'] for msg in msg_dict_list]
            return result if result else "Lo siento, señor. No tengo respuesta para su petición."

        except Exception as e:
            # Optional: log the error
            return f"Ha habido un error procesando su petición, señor. Error: {e}"

    def ask(self, prompt: str) -> str:
        """
        Main interaction method. Updates state and returns Jarvis's response.
        """
        self._update_chat_state(prompt)

        if self._chat_state == ChatState.NOT_INITIALIZED:
            return [AUTOMATIC_RESPONSE_IF_ID_FAILED]

        elif self._chat_state == ChatState.JARVIS_WELCOME_MESSAGE:
            return [self._get_welcome_message()]

        elif self._chat_state == ChatState.STARTING_CHAT:
            messages = [
                SystemMessage(content=self._build_background_prompt())
            ]
            if self.valid_user:
                messages.append(AIMessage(content=self._get_welcome_message()))
            messages.append(HumanMessage(content=prompt))
            return self._process_messages(messages)

        elif self._chat_state == ChatState.INITIALIZED:
            messages = [HumanMessage(content=prompt)]
            return self._process_messages(messages)
