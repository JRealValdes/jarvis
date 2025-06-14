from langchain.schema import AIMessage
from enums.core_enums import ModelEnum, IdentificationFailedProtocolEnum
from config import DEFAULT_MODEL, IDENTIFICATION_FAILED_PROTOCOL
from database.users.users_db import find_user_by_prompt
from agents.factory import build_agent, models_with_memory

AUTOMATIC_RESPONSE_IF_ID_FAILED = "Me temo que no puedo servirle sin identificación."

# === Caches globales ===
_sessions_cache: dict[tuple[ModelEnum, str], "JarvisSession"] = {}
_agents_cache: dict[ModelEnum, object] = {}

class JarvisSession:
    def __init__(self, model: ModelEnum = DEFAULT_MODEL, thread_id: str = "1"):
        self.model = model
        self.thread_id = thread_id
        self.valid_user = False
        self.user = None
        self.agent = self._load_agent()
        self.session_initialized = False
        self._chat_initialized = False

    def _load_agent(self):
        if self.model not in _agents_cache:
            _agents_cache[self.model] = build_agent(self.model)
        return _agents_cache[self.model]
    
    def get_welcome_message(self) -> str:
        gender_termination = "a" if self.user["is_female"] else "o"
        return f"Bienvenid{gender_termination}, {self.user['jarvis_name']}. ¿En qué puedo servirle hoy?"

    def _get_background_prompt(self) -> str | None:
        if self.valid_user:
            return (
                "Eres un mayordomo amigable, elegante y servicial llamado Jarvis. "
                f"Cuando te dirijas al usuario, usa siempre el nombre de '{self.user['jarvis_name']}', (hablando de usted). "
                f"El usuario es {'una mujer' if self.user['is_female'] else 'un hombre'}. "
            )
        elif IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES:
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
        elif IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE:
            return None
        else:
            raise ValueError(f"Identification protocol '{IDENTIFICATION_FAILED_PROTOCOL}' not recognized.")

    def _build_messages(self, question: str) -> list | None:
        """
        Builds the messages to be sent to the agent based on the question.
        If it returns None, the response will later be automatically generated: Welcome message or get-out message.
        """
        messages = []
        if not self.session_initialized:
            self._check_identity(question)
            if self.valid_user:
                self.session_initialized = True   # If user did not identify, they can still retry on next iteration
            return None
        
        if not self._chat_initialized:
            system_msg = self._get_background_prompt()
            if system_msg:
                messages.append({"role": "system", "content": system_msg})
                messages.append({"role": "assistant", "content": self.get_welcome_message()})
                self._chat_initialized = True
            else:
                return None

        if self.valid_user or IDENTIFICATION_FAILED_PROTOCOL == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES:
            messages.append({"role": "user", "content": question})
        else:
            return None
        return messages

    def _build_kwargs(self, messages: list) -> dict:
        kwargs = {"input": {"messages": messages}}
        if self.model in models_with_memory:
            kwargs["config"] = {"configurable": {"thread_id": self.thread_id}}
        return kwargs

    def _check_identity(self, question: str):
        if not self.valid_user:
            user = find_user_by_prompt(question)
            if user:
                self.valid_user = True
                self.user = user

    def ask(self, question: str) -> str:
        messages = self._build_messages(question)
        if messages is None:
            if self.valid_user:
                return self.get_welcome_message()
            else:
                return AUTOMATIC_RESPONSE_IF_ID_FAILED

        kwargs = self._build_kwargs(messages)
        response = self.agent.invoke(**kwargs)
        ai_messages = [
            msg.content for msg in response['messages']
            if isinstance(msg, AIMessage) and msg.content
        ]
        return ai_messages[-1] if ai_messages else "Lo siento, señor. No tengo respuesta para su petición."

def ask_jarvis(question: str, model: ModelEnum = DEFAULT_MODEL, thread_id: str = "1") -> str:
    session_key = (model, thread_id)
    if session_key not in _sessions_cache:
        _sessions_cache[session_key] = JarvisSession(model, thread_id)
    return _sessions_cache[session_key].ask(question)

def reset_cache():
    """Resets agents and sessions cache."""
    global _agents_cache
    global _sessions_cache
    _agents_cache = {}
    _sessions_cache = {}
