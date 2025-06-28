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


# === Global caches ===
_sessions_cache: dict[tuple[ModelEnum, str], "JarvisSession"] = {}
_agents_cache: dict[ModelEnum, object] = {}


class JarvisSession:
    """
    Manages a conversational session with Jarvis, including user identification,
    state transitions, and message processing via an LLM agent.
    """

    def __init__(self, model_enum: ModelEnum = DEFAULT_MODEL, thread_id: str = "1"):
        self.model_enum = model_enum
        self.thread_id = thread_id
        self.valid_user = False
        self.user = None
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
                "Hablas de usted."
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
        kwargs = {"input": {"messages": messages}}
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



            result = []
            for msg in response_messages[last_human_index + 1:]:
                if isinstance(msg, AIMessage) and 'tool_calls' in msg.additional_kwargs:
                    for tool_call in msg.additional_kwargs['tool_calls']:
                        result.append(f"Llamando a la función: {tool_call['function']['name']}")
                elif isinstance(msg, ToolMessage):
                    result.append(f"Resultado de la función {msg.name}: {msg.content}")
                else:
                    result.append(msg.content)

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


def ask_jarvis(prompt: str, model: ModelEnum = DEFAULT_MODEL, thread_id: str = "1") -> str:
    """
    Entry point for interacting with Jarvis via session cache.
    """
    session_key = (model, thread_id)
    if session_key not in _sessions_cache:
        _sessions_cache[session_key] = JarvisSession(model, thread_id)
    return _sessions_cache[session_key].ask(prompt)


def reset_cache():
    """
    Clears the cached agents and sessions.
    """
    global _agents_cache
    global _sessions_cache
    _agents_cache.clear()
    _sessions_cache.clear()
