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
    extract_avoid_constraints,
    format_avoid_constraints_for_prompt,
    format_preferences_for_prompt,
    job_preferences_path,
    load_job_preferences,
)
from jarvis.infrastructure.users.linkedin_reply_examples import (
    format_reply_examples_for_prompt,
    linkedin_reply_examples_path,
    load_linkedin_reply_example_entries,
)
from jarvis.infrastructure.users.message_language import resolve_reply_language

_DRAFT_SYSTEM_PROMPT = """\
You help the user draft a LinkedIn (or recruiter) reply.
Use the job preferences when present. Be honest about fit.
When sample replies are provided, treat them as style references only: match
their structure, length, greeting/closing, and phrasing habits. Adapt names,
companies, and facts to the new thread; do not copy an example verbatim.
Sample replies may be written in a different language than the required reply
language — never copy the sample language; rewrite in the required language.

HARD CONSTRAINTS (highest priority, override style samples and default LinkedIn
clichés):
1) Obey every item under "Phrases and patterns to avoid". Do not use those
phrases, patterns, or close paraphrases in any language. For example, if the
user forbids "I find it interesting, especially X", also forbid Spanish
variants such as "suena muy interesante, especialmente…". Prefer a specific,
personal appreciation instead of that template.
2) Obey "Reply language": the entire Proposed reply body MUST be written in
that language, even if the chat with the user, the preferences text, or the
sample replies use another language.

Never claim the message was sent. This is a draft only.

Respond in English with exactly these markdown sections:

## Fit assessment
One of: interested / maybe / decline. Brief reasons vs the preferences.

## Proposed reply
A copy-paste-ready message body only (no quotes wrapping the whole reply).
Write it entirely in the required reply language from the hard constraints.
Match professional tone from reply_style and the sample replies (style only).
The proposed reply must satisfy the hard avoid constraints.

## Confirmation required
Remind the user this is a draft. They must review, edit if needed, and
confirm before treating it as final. They send it themselves on LinkedIn.
"""


def generate_linkedin_reply_draft(
    message_context: str,
    user_notes: str,
    preferences: dict[str, Any] | None,
    *,
    reply_examples: list[str] | list[dict[str, str]] | None = None,
    reply_language: str | None = None,
    complete: Callable[[list], str] | None = None,
) -> str:
    """
    Build a LinkedIn reply draft from message context and preferences.

    Args:
        message_context: Pasted thread or description of the incoming message.
        user_notes: Optional extra instructions from the user.
        preferences: Loaded job preferences, or ``None``.
        reply_examples: Optional sample bodies or ``{label, body}`` entries
            for style matching (any language).
        reply_language: Optional explicit language override (``English`` /
            ``Spanish`` or aliases). When omitted, detected from
            ``message_context``.
        complete: Optional callable that takes a list of LangChain messages and
            returns the model text. Defaults to a ChatOpenAI completion.

    Returns:
        Structured draft text for the agent to show the user.
    """
    language = resolve_reply_language(
        message_context,
        override=reply_language,
    )
    prefs_block = format_preferences_for_prompt(preferences)
    avoid_block = format_avoid_constraints_for_prompt(
        extract_avoid_constraints(preferences)
    )
    examples_block = format_reply_examples_for_prompt(reply_examples or [])
    notes = user_notes.strip() or "(none)"
    language_block = (
        f"Required language for the Proposed reply: {language}.\n"
        "Write every sentence of the Proposed reply in that language. "
        "Sample replies are style-only — adapt phrasing into the required "
        "language; do not keep the sample language because samples match."
    )
    human = (
        f"## Phrases and patterns to avoid (HARD CONSTRAINTS)\n{avoid_block}\n\n"
        f"## Reply language (HARD CONSTRAINT)\n{language_block}\n\n"
        f"## Job preferences\n{prefs_block}\n\n"
        f"## Sample replies (style reference; any language)\n{examples_block}\n\n"
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
    reply_language: str = "",
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Draft a LinkedIn or recruiter reply using the user's job preferences.

    Call this when the user asks to reply to a LinkedIn message, a recruiter
    outreach, or pastes such a thread. Loads job preferences and optional
    sample replies from data/users/<real_name>/ for style matching. Detects
    the recruiter's language from message_context (Spanish or English) and
    drafts the proposed reply in that language unless reply_language overrides
    it. The result is always a draft: the user must confirm before treating
    it as final. Jarvis does not send messages.

    Parameters:
    - message_context: the incoming message or thread text (required)
    - user_notes: optional extra guidance (e.g. "politely decline", "ask for salary band")
    - reply_language: optional override for the proposed reply language
      ("English", "Spanish", "en", "es"). Leave empty to detect from
      message_context.
    - real_name: injected user id; loads job_preferences.yaml and
      linkedin_reply_examples.yaml under data/users/<real_name>/
    """
    try:
        if not message_context or not message_context.strip():
            return (
                "Cannot draft a reply: message_context is empty. "
                "Ask the user to paste the LinkedIn thread or describe it."
            )
        normalized = (real_name or "").strip().lower()
        preferences = load_job_preferences(normalized) if normalized else None
        example_entries = (
            load_linkedin_reply_example_entries(normalized) if normalized else []
        )
        path = job_preferences_path(normalized) if normalized else None
        examples_path = (
            linkedin_reply_examples_path(normalized) if normalized else None
        )
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
        if example_entries and examples_path is not None:
            examples_status = (
                f"Loaded {len(example_entries)} sample reply(ies) "
                f"from {examples_path}."
            )
        elif examples_path is not None:
            examples_status = (
                f"No sample replies file found (expected {examples_path}). "
                "Drafting without style examples."
            )
        else:
            examples_status = "No sample replies loaded."
        language = resolve_reply_language(
            message_context,
            override=reply_language or None,
        )
        override_note = (
            " (explicit override)"
            if (reply_language or "").strip()
            else " (detected from message_context)"
        )
        language_status = f"Reply language: {language}{override_note}."
        draft = generate_linkedin_reply_draft(
            message_context,
            user_notes,
            preferences,
            reply_examples=example_entries,
            reply_language=language,
        )
        return (
            f"{prefs_status}\n{examples_status}\n{language_status}\n\n{draft}\n\n"
            "---\n"
            "DRAFT ONLY — wait for the user's confirmation before treating "
            "this reply as final. Do not claim it was sent on LinkedIn."
        )
    except Exception as exc:
        return f"Failed to draft LinkedIn reply: {exc}"
