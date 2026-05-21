"""Chat session orchestration, agent cache, and LLM invocation."""

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
    Summarize global agent and session cache state.

    Returns:
        Dict with keys ``agents_cache_count``, ``sessions_cache_count``,
        ``agent_models`` (names), and ``sessions`` (model/thread pairs).
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
    Report whether a session is cached for the given thread and model.

    Args:
        thread_id: Conversation id (e.g. user real_name).
        model: Model associated with the session.

    Returns:
        True if key (model, thread_id) is in the cache.
    """
    return (model, thread_id) in _sessions_cache


def ask_jarvis(
    prompt: str,
    model: ModelEnum = DEFAULT_MODEL,
    thread_id: str = "1",
    user_info: dict | None = None,
) -> list[str]:
    """
    Main entry point to send a message to Jarvis.

    Args:
        prompt: User message.
        model: LLM model to use.
        thread_id: Thread / session identifier.
        user_info: Authenticated user dict (API); None in CLI without JWT.

    Returns:
        List of response text fragments for the user.
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
    Remove the cached session and agent memory thread if applicable.

    Args:
        thread_id: Thread to clear.
        model: Model associated with the thread.

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
    Clear agent and session caches completely.

    Returns:
        None.
    """
    global _agents_cache, _sessions_cache
    _agents_cache.clear()
    _sessions_cache.clear()


reset_cache = reset_cache_global
"""Alias used by the Gradio UI (``app.py``)."""


def _parse_message_list(messages: list) -> list[dict]:
    """
    Convert LangChain messages to ``{role, content}`` dicts for the API.

    Args:
        messages: List of SystemMessage, HumanMessage, AIMessage, ToolMessage.

    Returns:
        List of dicts with roles ``system``, ``user``, or ``assistant``.
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
    Return parsed message history for a thread if the session is cached.

    Args:
        thread_id: Conversation identifier.
        model: Cached agent model.

    Returns:
        List of ``{role, content}`` messages; empty if no session or on failure.
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
    Orchestrates a conversation turn: state, prompts, and LLM agent.

    Attributes:
        model_enum: Session LLM model.
        thread_id: Thread identifier.
        valid_user: Whether the user is identified or authenticated.
        user: User data dict (real_name, jarvis_name, etc.).
        agent: Agent instance from the global cache.
    """

    def __init__(
        self,
        model_enum: ModelEnum = DEFAULT_MODEL,
        thread_id: str = "1",
        user_info: dict | None = None,
    ) -> None:
        """
        Args:
            model_enum: Model to use.
            thread_id: Conversation thread.
            user_info: API-authenticated user; None without JWT.
        """
        self.model_enum = model_enum
        self.thread_id = thread_id
        self.valid_user = bool(user_info)
        self.user = user_info
        self.agent = self._load_or_build_agent()
        self._chat_state = ChatState.NOT_INITIALIZED

    def _load_or_build_agent(self) -> object:
        """
        Get the agent from the global cache or build it.

        Returns:
            Agent instance (Basic, Memory, or MCP).
        """
        if self.model_enum not in _agents_cache:
            _agents_cache[self.model_enum] = build_agent(self.model_enum)
        return _agents_cache[self.model_enum]

    def _try_identify_user(self, prompt: str) -> None:
        """
        Try to identify the user from a pattern in the prompt.

        Args:
            prompt: User message.

        Returns:
            None. Updates ``valid_user`` and ``user`` on match.
        """
        user = find_user_by_prompt(prompt)
        if user:
            self.valid_user = True
            self.user = user

    def _update_chat_state(self, prompt: str) -> None:
        """
        Advance the state machine and apply memory effects if needed.

        Args:
            prompt: Latest user message.

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
        Build kwargs for ``agent.invoke``.

        Args:
            messages: LangChain message list.

        Returns:
            Dict with ``input`` and optionally ``config`` (thread_id).
        """
        real_name = self.user["real_name"] if self.user else ""
        kwargs = {"input": {"messages": messages, "real_name": real_name}}
        if self.model_enum in models_with_memory:
            kwargs["config"] = {"configurable": {"thread_id": self.thread_id}}
        return kwargs

    def _process_messages(self, messages: list) -> list[str] | str:
        """
        Invoke the agent and extract assistant replies from the state.

        Args:
            messages: Messages to send to the graph.

        Returns:
            List of response strings, or an error message as str/list.
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
        Process a user turn and return Jarvis's reply.

        Args:
            prompt: User message.

        Returns:
            List of response strings or a single message depending on state.
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
