"""Chat session orchestration and LLM invocation."""

import logging
import sqlite3

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from jarvis.agents.factory import build_agent
from jarvis.agents.mcp_session import get_mcp_tool_session
from jarvis.agents.protocol import JarvisAgent
from jarvis.agents.session.cache import (
    get_agents_cache,
    get_sessions_cache,
    invalidate_agents_cache,
)
from jarvis.agents.session.history import load_thread_snapshot, parse_message_list
from jarvis.core.config import (
    DEFAULT_MODEL,
    IDENTIFICATION_FAILED_PROTOCOL,
    LOCAL_THREAD_ID,
    USE_MCP,
)
from jarvis.core.enums import ModelEnum
from jarvis.domain.chat.chat_state import (
    ChatState,
    compute_next_chat_state,
    should_clear_agent_thread_on_identification,
)
from jarvis.domain.users.prompts import (
    AUTOMATIC_RESPONSE_IF_ID_FAILED,
    build_background_prompt,
    get_welcome_message,
)
from jarvis.infrastructure.persistence.users.identification import find_user_by_prompt
from jarvis.infrastructure.persistence.users.repository import get_user_by_field

logger = logging.getLogger(__name__)


class JarvisSession:
    """
    Orchestrates a conversation turn: state, prompts, and LLM agent.

    Attributes:
        model_enum: Session LLM model.
        thread_id: Thread identifier.
        valid_user: Whether the user is identified or authenticated.
        user: User data dict (real_name, jarvis_name, etc.).
        agent: Agent from the global cache (``JarvisAgent``).
    """

    def __init__(
        self,
        model_enum: ModelEnum = DEFAULT_MODEL,
        thread_id: str = LOCAL_THREAD_ID,
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
        self._chat_state = ChatState.NOT_INITIALIZED
        self._restore_from_checkpoint()

    def apply_authenticated_user(self, user_info: dict) -> None:
        """
        Replace the session identity with a newly authenticated user.

        Args:
            user_info: Decoded JWT claims or equivalent user dict.

        Returns:
            None.
        """
        self.user = user_info
        self.valid_user = True

    def _restore_from_checkpoint(self) -> None:
        """
        Align in-memory chat state with a thread that already has messages.

        A process restart used to rebuild ``ChatState.NOT_INITIALIZED`` and
        send the welcome flow again. When the checkpointer already holds the
        thread, continue from ``INITIALIZED``. If the caller did not pass a
        user, restore one from the checkpoint ``real_name``.

        Returns:
            None. Leaves the session uninitialized when the thread is empty
            or the checkpoint cannot be read.
        """
        try:
            snapshot = load_thread_snapshot(self.model_enum, self.thread_id)
        except Exception:
            logger.exception(
                "Could not read checkpoint for thread %s (%s)",
                self.thread_id,
                self.model_enum.name,
            )
            return
        if snapshot is None:
            return
        self._chat_state = ChatState.INITIALIZED
        if self.user is not None:
            return
        restored = _user_for_real_name(snapshot["real_name"])
        if restored is None:
            return
        self.user = restored
        self.valid_user = True

    @property
    def agent(self) -> JarvisAgent:
        """
        Agent for this session's model.

        Reloads from the global cache after MCP reconnect invalidates agents.
        """
        return self._load_or_build_agent()

    def _load_or_build_agent(self) -> JarvisAgent:
        """
        Get the agent from the global cache or build it.

        Returns:
            Agent that implements ``JarvisAgent``.
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
            Dict with ``input`` and ``config`` (thread_id for the checkpointer).
        """
        real_name = self.user["real_name"] if self.user else ""
        return {
            "input": {"messages": messages, "real_name": real_name},
            "config": {"configurable": {"thread_id": self.thread_id}},
        }

    def _direct_reply(self, prompt: str) -> list[str] | None:
        """
        Advance chat state and return a reply that does not call the model.

        Args:
            prompt: User message.

        Returns:
            Reply strings, or None when the model must run.
        """
        self._update_chat_state(prompt)
        if self._chat_state == ChatState.NOT_INITIALIZED:
            return [AUTOMATIC_RESPONSE_IF_ID_FAILED]
        if self._chat_state == ChatState.JARVIS_WELCOME_MESSAGE:
            return [get_welcome_message(self.user)]
        if self._chat_state in (ChatState.STARTING_CHAT, ChatState.INITIALIZED):
            return None
        return [AUTOMATIC_RESPONSE_IF_ID_FAILED]

    def _messages_for_model(self, prompt: str) -> list:
        """
        Build the LangChain messages for a model turn.

        Args:
            prompt: User message.

        Returns:
            Messages for ``STARTING_CHAT`` (with system context) or a single human turn.
        """
        if self._chat_state == ChatState.STARTING_CHAT:
            messages = [
                SystemMessage(
                    content=build_background_prompt(self.valid_user, self.user)
                )
            ]
            if self.valid_user:
                messages.append(AIMessage(content=get_welcome_message(self.user)))
            messages.append(HumanMessage(content=prompt))
            return messages
        return [HumanMessage(content=prompt)]

    def _replies_from_state(self, response: dict) -> list[str]:
        """
        Extract assistant text that follows the latest human message.

        Args:
            response: Final graph state.

        Returns:
            Reply strings. A fallback sentence when the model returned nothing.
        """
        response_messages = response.get("messages", [])
        last_human_index = max(
            (
                i
                for i, msg in enumerate(response_messages)
                if isinstance(msg, HumanMessage)
            ),
            default=-1,
        )
        msg_dict_list = parse_message_list(response_messages[last_human_index + 1 :])
        result = [msg["content"] for msg in msg_dict_list]
        return result if result else ["I'm sorry, sir. I have no response for your request."]

    async def _run_model(self, messages: list) -> list[str]:
        """
        Await the agent and extract assistant replies from the state.

        Args:
            messages: Messages to send to the graph.

        Returns:
            List of response strings (never empty on success path).
        """
        try:
            response = await self.agent.invoke(**self._build_agent_kwargs(messages))
            return self._replies_from_state(response)
        except Exception as e:
            return [f"There was an error processing your request, sir. Error: {e}"]

    async def handle_turn(self, prompt: str) -> list[str]:
        """
        Run one conversation turn for this session.

        Advances the chat state machine and, when needed, invokes the model.

        Args:
            prompt: User message.

        Returns:
            List of response strings for the user.
        """
        direct = self._direct_reply(prompt)
        if direct is not None:
            return direct
        return await self._run_model(self._messages_for_model(prompt))


def _session_for(
    model: ModelEnum,
    thread_id: str,
    user_info: dict | None,
) -> JarvisSession:
    """
    Return the cached session for a model and thread, creating it if needed.

    Args:
        model: LLM model to use.
        thread_id: Thread / session identifier.
        user_info: Authenticated user dict, or None.

    Returns:
        Session stored under ``(model, thread_id)``.
    """
    sessions_cache = get_sessions_cache()
    session_key = (model, thread_id)
    if session_key not in sessions_cache:
        sessions_cache[session_key] = JarvisSession(model, thread_id, user_info)
    elif user_info:
        sessions_cache[session_key].apply_authenticated_user(user_info)
    return sessions_cache[session_key]


async def _ensure_mcp_ready() -> None:
    """
    Connect or reconnect the process-wide MCP session when enabled.

    Rebuilds cached agents after a reconnect so graphs bind the new tools.

    Returns:
        None.
    """
    if not USE_MCP:
        return
    session = get_mcp_tool_session()
    was_broken = session.is_broken
    await session.ensure_ready()
    if was_broken:
        invalidate_agents_cache()


def _user_for_real_name(real_name: str) -> dict | None:
    """
    Look up a user row by ``real_name``.

    Args:
        real_name: Name stored on the checkpoint. Empty skips the lookup.

    Returns:
        User dict, or None when the name is blank or the users database
        cannot be read.
    """
    if not real_name.strip():
        return None
    try:
        return get_user_by_field("real_name", real_name, is_sensitive=False)
    except sqlite3.Error:
        logger.warning(
            "Could not restore user %s from the users database", real_name
        )
        return None


async def ask_jarvis(
    prompt: str,
    model: ModelEnum = DEFAULT_MODEL,
    thread_id: str = LOCAL_THREAD_ID,
    user_info: dict | None = None,
) -> list[str]:
    """
    Public entry point to send a message to Jarvis.

    Resolves the cached session, ensures MCP is ready when enabled, and runs
    one turn. Call from an async context (CLI loop, FastAPI, Gradio).

    Args:
        prompt: User message.
        model: LLM model to use.
        thread_id: Thread / session identifier.
        user_info: Authenticated user dict (API); None in CLI without JWT.

    Returns:
        List of response text fragments for the user.
    """
    await _ensure_mcp_ready()
    return await _session_for(model, thread_id, user_info).handle_turn(prompt)
