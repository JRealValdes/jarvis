"""LangChain tools to show and register per-user LinkedIn reply style samples."""

from __future__ import annotations

from typing import Annotated, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import InjectedState

from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import resolve_openai_chat_model_id
from jarvis.infrastructure.users.linkedin_reply_examples import (
    append_linkedin_reply_example,
    linkedin_reply_examples_path,
    load_linkedin_reply_example_entries,
)
from jarvis.infrastructure.users.message_language import detect_message_language

_TRANSLATE_SYSTEM_PROMPT = """\
You translate LinkedIn reply style samples into English.
Preserve meaning, tone, structure, greetings/closings, and proper names.
Do not paraphrase, shorten, expand, or improve the writing beyond translation.
Return only the translated message body, with no quotes or commentary.
"""


def prepare_english_example_body(
    message_body: str,
    *,
    translate: Callable[[str], str] | None = None,
) -> tuple[str, bool]:
    """
    Return a sample body ready to store in English.

    English text is returned unchanged. Non-English text is translated; that
    translation is the only allowed modification from the approved wording.

    Args:
        message_body: Approved sample reply text (any language).
        translate: Optional callable that translates a non-English body to
            English. Defaults to a low-temperature ChatOpenAI completion.

    Returns:
        ``(english_body, was_translated)``.
    """
    text = message_body.strip()
    if detect_message_language(text) == "English":
        return text, False
    if translate is None:
        translate = _default_translate_to_english
    translated = translate(text).strip()
    if not translated:
        raise ValueError("Translation produced an empty English body.")
    return translated, True


def _default_translate_to_english(text: str) -> str:
    """Translate ``text`` to English via ChatOpenAI."""
    llm = ChatOpenAI(
        model=resolve_openai_chat_model_id(ModelEnum.GPT_4O_MINI),
        temperature=0,
    )
    response = llm.invoke(
        [
            SystemMessage(content=_TRANSLATE_SYSTEM_PROMPT),
            HumanMessage(content=text),
        ]
    )
    content = response.content
    return content if isinstance(content, str) else str(content)


@tool
def show_linkedin_reply_examples_tool(
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Show the user's saved LinkedIn reply style examples.

    Call when the user asks what sample replies are stored, or before adding more.
    Does not modify any files.

    Parameters:
    - real_name: injected user id for data/users/<real_name>/linkedin_reply_examples.yaml
    """
    normalized = (real_name or "").strip()
    if not normalized:
        return (
            "Cannot show LinkedIn reply examples: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    path = linkedin_reply_examples_path(normalized)
    entries = load_linkedin_reply_example_entries(normalized)
    if not entries:
        return (
            f"No LinkedIn reply examples found at {path}. "
            "Ask the user to paste a complete sample message, then call "
            "add_linkedin_reply_example_tool with confirmed=true after they approve."
        )
    parts: list[str] = [f"LinkedIn reply examples at {path} ({len(entries)}):", ""]
    for index, entry in enumerate(entries, start=1):
        label = entry.get("label") or "(no label)"
        parts.append(f"### Example {index}: {label}")
        parts.append(entry["body"])
        parts.append("")
    return "\n".join(parts).rstrip()


@tool
def add_linkedin_reply_example_tool(
    message_body: str,
    label: str = "",
    confirmed: bool = False,
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Append one complete LinkedIn reply sample for style matching when drafting.

    Call only when the user explicitly asks to save a reply as a style example
    (not when they merely approve a draft for copy-paste). Samples are stored
    in English. Pass the approved wording; do not regenerate, paraphrase, or
    call draft_linkedin_reply_tool again. If the text is not English, this tool
    translates it to English (translation only—no other edits). Show the
    English sample that will be saved, then call only after they explicitly
    confirm the save. Never call with confirmed=true without that approval.

    Parameters:
    - message_body: the complete sample reply text as approved (required);
      non-English bodies are translated to English before storage
    - label: optional short English label (e.g. "polite decline remote")
    - confirmed: must be true to write; false refuses the write
    - real_name: injected user id
    """
    normalized = (real_name or "").strip()
    if not normalized:
        return (
            "Cannot add LinkedIn reply example: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    if not message_body or not message_body.strip():
        return (
            "Cannot add LinkedIn reply example: message_body is empty. "
            "Ask the user to paste a complete sample message."
        )
    try:
        english_body, was_translated = prepare_english_example_body(message_body)
    except ValueError as exc:
        return f"Cannot add LinkedIn reply example: {exc}"
    except Exception as exc:
        return f"Failed to prepare LinkedIn reply example in English: {exc}"

    translation_note = (
        "Translated to English for storage (meaning/tone preserved; no other edits).\n\n"
        if was_translated
        else ""
    )
    if not confirmed:
        preview_label = label.strip() or "(no label)"
        return (
            "Refused to write: confirmed is false. Present this English sample "
            "to the user, wait for explicit approval, then call again with "
            f"confirmed=true.\n\n{translation_note}"
            f"Label: {preview_label}\n\n"
            f"```\n{english_body}\n```"
        )
    try:
        path = append_linkedin_reply_example(
            normalized,
            english_body,
            label=label,
        )
        entries = load_linkedin_reply_example_entries(normalized)
        return (
            f"Added LinkedIn reply example at {path}. "
            f"Total examples: {len(entries)}.\n\n{translation_note}"
            f"Latest sample:\n```\n{english_body}\n```"
        )
    except ValueError as exc:
        return f"Cannot add LinkedIn reply example: {exc}"
    except Exception as exc:
        return f"Failed to add LinkedIn reply example: {exc}"
