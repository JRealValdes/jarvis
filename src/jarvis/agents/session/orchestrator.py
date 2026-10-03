"""Chat session orchestration and LLM invocation."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from jarvis.agents.factory import build_agent, models_with_memory
from jarvis.agents.session.cache import get_agents_cache, get_sessions_cache
from jarvis.agents.session.history import parse_message_list
from jarvis.core.config import DEFAULT_MODEL, IDENTIFICATION_FAILED_PROTOCOL
from jarvis.core.enums import ModelEnum
from jarvis.domain.chat.chat_state import (
    ChatState,
    compute_next_chat_state,
    should_clear_agent_thread_on_identification,
)
from jarvis.infrastructure.persistence.users.identification import find_user_by_prompt
from jarvis.domain.users.prompts import (
    AUTOMATIC_RESPONSE_IF_ID_FAILED,
    build_background_prompt,
    get_welcome_message,
)


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
        agents_cache = get_agents_cache()
        if self.model_enum not in agents_cache:
            agents_cache[self.model_enum] = build_agent(self.model_enum)
        return agents_cache[self.model_enum]

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
                (
                    i
                    for i, msg in enumerate(response_messages)
                    if isinstance(msg, HumanMessage)
                ),
                default=-1,
            )
            msg_dict_list = parse_message_list(
                response_messages[last_human_index + 1 :]
            )
            result = [msg["content"] for msg in msg_dict_list]
            return (
                result
                if result
                else "I'm sorry, sir. I have no response for your request."
            )
        except Exception as e:
            return f"There was an error processing your request, sir. Error: {e}"

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
                SystemMessage(
                    content=build_background_prompt(self.valid_user, self.user)
                )
            ]
            if self.valid_user:
                messages.append(AIMessage(content=get_welcome_message(self.user)))
            messages.append(HumanMessage(content=prompt))
            return self._process_messages(messages)

        if self._chat_state == ChatState.INITIALIZED:
            messages = [HumanMessage(content=prompt)]
            return self._process_messages(messages)

        return [AUTOMATIC_RESPONSE_IF_ID_FAILED]


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
    sessions_cache = get_sessions_cache()
    session_key = (model, thread_id)
    if session_key not in sessions_cache:
        sessions_cache[session_key] = JarvisSession(model, thread_id, user_info)
    result = sessions_cache[session_key].ask(prompt)

    if isinstance(result, list):
        return result
    return [result]
