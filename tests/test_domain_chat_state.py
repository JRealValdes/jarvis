"""Unit tests for the chat state machine (no LLM)."""

from jarvis.domain.chat.chat_state import (
    ChatState,
    compute_next_chat_state,
    should_clear_agent_thread_on_identification,
)
from jarvis.core.enums import IdentificationFailedProtocolEnum


def test_not_initialized_valid_user_welcome():
    state = compute_next_chat_state(
        ChatState.NOT_INITIALIZED,
        valid_user=True,
        was_previously_invalid=True,
        identification_protocol=IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
    )
    assert state == ChatState.JARVIS_WELCOME_MESSAGE


def test_not_initialized_automatic_response_stays_uninitialized():
    state = compute_next_chat_state(
        ChatState.NOT_INITIALIZED,
        valid_user=False,
        was_previously_invalid=True,
        identification_protocol=IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
    )
    assert state == ChatState.NOT_INITIALIZED


def test_not_initialized_hostile_starts_chat():
    state = compute_next_chat_state(
        ChatState.NOT_INITIALIZED,
        valid_user=False,
        was_previously_invalid=True,
        identification_protocol=IdentificationFailedProtocolEnum.HOSTILE_RESPONSES,
    )
    assert state == ChatState.STARTING_CHAT


def test_welcome_to_starting_to_initialized():
    s1 = compute_next_chat_state(
        ChatState.JARVIS_WELCOME_MESSAGE,
        valid_user=True,
        was_previously_invalid=False,
        identification_protocol=IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
    )
    assert s1 == ChatState.STARTING_CHAT
    s2 = compute_next_chat_state(
        s1,
        valid_user=True,
        was_previously_invalid=False,
        identification_protocol=IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
    )
    assert s2 == ChatState.INITIALIZED


def test_initialized_late_identification_returns_welcome():
    state = compute_next_chat_state(
        ChatState.INITIALIZED,
        valid_user=True,
        was_previously_invalid=True,
        identification_protocol=IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
    )
    assert state == ChatState.JARVIS_WELCOME_MESSAGE


def test_should_clear_thread_on_late_identification():
    assert should_clear_agent_thread_on_identification(
        ChatState.INITIALIZED,
        was_previously_invalid=True,
        valid_user=True,
    )
    assert not should_clear_agent_thread_on_identification(
        ChatState.INITIALIZED,
        was_previously_invalid=False,
        valid_user=True,
    )
