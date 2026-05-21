"""Máquina de estados del flujo conversacional de Jarvis."""

from enum import Enum

from enums.core_enums import IdentificationFailedProtocolEnum


class ChatState(Enum):
    """Estados del flujo de conversación de una sesión Jarvis."""

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
    Calcula el siguiente estado sin efectos secundarios (sin I/O ni memoria).

    Args:
        current: Estado actual de la sesión.
        valid_user: Si el usuario está identificado o autenticado.
        was_previously_invalid: True si antes de este turno no había usuario válido.
        identification_protocol: Comportamiento cuando falla la identificación.

    Returns:
        Nuevo ChatState tras aplicar las transiciones del turno.
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
    Indica si hay que borrar el hilo del agente tras identificar al usuario en chat activo.

    Args:
        current: Estado antes de ``compute_next_chat_state``.
        was_previously_invalid: Usuario inválido al inicio del turno.
        valid_user: Usuario válido tras intentar identificar.

    Returns:
        True si se debe llamar a ``memory.delete_thread``.
    """
    return (
        current == ChatState.INITIALIZED
        and was_previously_invalid
        and valid_user
    )
