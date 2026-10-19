"""LangChain tools to show and register per-user LinkedIn reply style samples."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from jarvis.infrastructure.users.linkedin_reply_examples import (
    append_linkedin_reply_example,
    linkedin_reply_examples_path,
    load_linkedin_reply_example_entries,
)


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
    (not when they merely approve a draft for copy-paste). Pass message_body as
    the exact wording and language they approved—do not regenerate, paraphrase,
    or call draft_linkedin_reply_tool again. Show the sample back, then call
    only after they explicitly confirm the save. Never call with
    confirmed=true without that approval.

    Parameters:
    - message_body: the complete sample reply text, verbatim (required)
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
    if not confirmed:
        preview_label = label.strip() or "(no label)"
        return (
            "Refused to write: confirmed is false. Present this sample to the "
            "user, wait for explicit approval, then call again with "
            f"confirmed=true.\n\nLabel: {preview_label}\n\n"
            f"```\n{message_body.strip()}\n```"
        )
    try:
        path = append_linkedin_reply_example(
            normalized,
            message_body,
            label=label,
        )
        entries = load_linkedin_reply_example_entries(normalized)
        return (
            f"Added LinkedIn reply example at {path}. "
            f"Total examples: {len(entries)}.\n\n"
            f"Latest sample:\n```\n{message_body.strip()}\n```"
        )
    except ValueError as exc:
        return f"Cannot add LinkedIn reply example: {exc}"
    except Exception as exc:
        return f"Failed to add LinkedIn reply example: {exc}"
