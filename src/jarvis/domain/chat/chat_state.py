"""State machine for the Jarvis conversational flow."""

from enum import Enum

from core.enums import IdentificationFailedProtocolEnum


class ChatState(Enum):
    """Conversation flow states for a Jarvis session."""

    NOT_INITIALIZED = "NOT_INITIALIZED"
    JARVIS_WELCOME_MESSAGE = "JARVIS_WELCOME_MESSAGE"
    STARTING_CHAT = "STARTING_CHAT"
    INITIALIZED = "INITIALIZED"


def compute_next_chat_state(
    current: ChatState,
    *,
    valid_user: bool,
    was_previously_invalid: bool,
    identification_protocol: IdentificationFailedProtocolEnum,
) -> ChatState:
    """
    Compute the next state with no side effects (no I/O or memory).

    Args:
        current: Current session state.
        valid_user: Whether the user is identified or authenticated.
        was_previously_invalid: True if there was no valid user before this turn.
        identification_protocol: Behavior when identification fails.

    Returns:
        New ChatState after applying turn transitions.
    """
    if current == ChatState.NOT_INITIALIZED:
        if valid_user:
            return ChatState.JARVIS_WELCOME_MESSAGE
        if identification_protocol == IdentificationFailedProtocolEnum.HOSTILE_RESPONSES:
            return ChatState.STARTING_CHAT
        return ChatState.NOT_INITIALIZED

    if current == ChatState.JARVIS_WELCOME_MESSAGE:
        return ChatState.STARTING_CHAT

    if current == ChatState.STARTING_CHAT:
        return ChatState.INITIALIZED

    if current == ChatState.INITIALIZED:
        if was_previously_invalid and valid_user:
            return ChatState.JARVIS_WELCOME_MESSAGE
        return ChatState.INITIALIZED

    return current


def should_clear_agent_thread_on_identification(
    current: ChatState,
    *,
    was_previously_invalid: bool,
    valid_user: bool,
) -> bool:
    """
    Whether to clear the agent thread after identifying the user during active chat.

    Args:
        current: State before ``compute_next_chat_state``.
        was_previously_invalid: User was invalid at the start of the turn.
        valid_user: User is valid after identification attempt.

    Returns:
        True if ``memory.delete_thread`` should be called.
    """
    return (
        current == ChatState.INITIALIZED
        and was_previously_invalid
        and valid_user
    )
