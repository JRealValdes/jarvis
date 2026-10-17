"""LangChain tool to draft LinkedIn replies using per-user job preferences."""

from __future__ import annotations

from typing import Annotated, Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import InjectedState

from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import resolve_openai_chat_model_id
from jarvis.infrastructure.users.job_preferences import (
    format_preferences_for_prompt,
    job_preferences_path,
    load_job_preferences,
)

_DRAFT_SYSTEM_PROMPT = """\
You help the user draft a LinkedIn (or recruiter) reply.
Use the job preferences when present. Be honest about fit.
Never claim the message was sent. This is a draft only.

Respond in English with exactly these markdown sections:

## Fit assessment
One of: interested / maybe / decline. Brief reasons vs the preferences.

## Proposed reply
A copy-paste-ready message body only (no quotes wrapping the whole reply).
Match the recruiter language if the preferences say so; otherwise use a
professional tone consistent with reply_style.

## Confirmation required
Remind the user this is a draft. They must review, edit if needed, and
confirm before treating it as final. They send it themselves on LinkedIn.
"""


def generate_linkedin_reply_draft(
    message_context: str,
    user_notes: str,
    preferences: dict[str, Any] | None,
    *,
    complete: Callable[[list], str] | None = None,
) -> str:
    """
    Build a LinkedIn reply draft from message context and preferences.

    Args:
        message_context: Pasted thread or description of the incoming message.
        user_notes: Optional extra instructions from the user.
        preferences: Loaded job preferences, or ``None``.
        complete: Optional callable that takes a list of LangChain messages and
            returns the model text. Defaults to a ChatOpenAI completion.

    Returns:
        Structured draft text for the agent to show the user.
    """
    prefs_block = format_preferences_for_prompt(preferences)
    notes = user_notes.strip() or "(none)"
    human = (
        f"## Job preferences\n{prefs_block}\n\n"
        f"## Incoming message / thread\n{message_context.strip()}\n\n"
        f"## Extra notes from the user\n{notes}\n"
    )
    messages = [
        SystemMessage(content=_DRAFT_SYSTEM_PROMPT),
        HumanMessage(content=human),
    ]
    if complete is None:
        llm = ChatOpenAI(
            model=resolve_openai_chat_model_id(ModelEnum.GPT_4O_MINI),
            temperature=0.3,
        )
        response = llm.invoke(messages)
        content = response.content
        return content if isinstance(content, str) else str(content)
    return complete(messages)


@tool
def draft_linkedin_reply_tool(
    message_context: str,
    user_notes: str = "",
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Draft a LinkedIn or recruiter reply using the user's job preferences.

    Call this when the user asks to reply to a LinkedIn message, a recruiter
    outreach, or pastes such a thread. The result is always a draft: the user
    must confirm before treating it as final. Jarvis does not send messages.

    Parameters:
    - message_context: the incoming message or thread text (required)
    - user_notes: optional extra guidance (e.g. "politely decline", "ask for salary band")
    - real_name: injected user id used to load data/users/<real_name>/job_preferences.yaml
    """
    try:
        if not message_context or not message_context.strip():
            return (
                "Cannot draft a reply: message_context is empty. "
                "Ask the user to paste the LinkedIn thread or describe it."
            )
        normalized = (real_name or "").strip().lower()
        preferences = load_job_preferences(normalized) if normalized else None
        path = job_preferences_path(normalized) if normalized else None
        prefs_status = (
            f"Loaded preferences from {path}."
            if preferences is not None and path is not None
            else (
                "No job preferences file found for this user "
                f"(expected {path}). Drafting without personal criteria."
                if path is not None
                else "No real_name in session; drafting without personal criteria."
            )
        )
        draft = generate_linkedin_reply_draft(
            message_context,
            user_notes,
            preferences,
        )
        return (
            f"{prefs_status}\n\n{draft}\n\n"
            "---\n"
            "DRAFT ONLY — wait for the user's confirmation before treating "
            "this reply as final. Do not claim it was sent on LinkedIn."
        )
    except Exception as exc:
        return f"Failed to draft LinkedIn reply: {exc}"
