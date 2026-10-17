"""LangChain tools to show and save per-user job / LinkedIn reply preferences."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from jarvis.infrastructure.users.job_preferences import (
    format_preferences_for_prompt,
    job_preferences_path,
    load_job_preferences,
    parse_preferences_yaml,
    save_job_preferences,
)


@tool
def show_job_preferences_tool(
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Show the current job / LinkedIn reply preferences for the session user.

    Call this when the user asks what their preferences are, or before updating
    them. Does not modify any files.

    Parameters:
    - real_name: injected user id for data/users/<real_name>/job_preferences.yaml
    """
    normalized = (real_name or "").strip()
    if not normalized:
        return (
            "Cannot show job preferences: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    path = job_preferences_path(normalized)
    preferences = load_job_preferences(normalized)
    if preferences is None:
        return (
            f"No job preferences file found at {path}. "
            "Interview the user about reply_style and job_criteria, then call "
            "save_job_preferences_tool with confirmed=true after they approve."
        )
    body = format_preferences_for_prompt(preferences)
    return f"Job preferences at {path}:\n\n```yaml\n{body}\n```"


@tool
def save_job_preferences_tool(
    preferences_yaml: str,
    confirmed: bool = False,
    replace_all: bool = False,
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Save job / LinkedIn reply preferences for the session user.

    Interview the user about reply_style and job_criteria (salary, work mode,
    contract types, tech likes/dislikes, dealbreakers, notes, tone, language).
    Show a clear summary of what will be written, then call this tool only after
    they explicitly confirm. Never call with confirmed=true without that approval.

    Always pass preferences_yaml in English: translate the user's answers into
    English for every string value (and keep keys in English). Do not save
    Spanish or other non-English preference text in the YAML file.

    Parameters:
    - preferences_yaml: English YAML mapping aligned with the example
      job_preferences.yaml (top-level keys such as reply_style and job_criteria)
    - confirmed: must be true to write; false refuses the write (use after user OK)
    - replace_all: if true, replace the whole file; if false (default), merge
    - real_name: injected user id
    """
    normalized = (real_name or "").strip()
    if not normalized:
        return (
            "Cannot save job preferences: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    if not confirmed:
        return (
            "Refused to write: confirmed is false. Present the proposed YAML to "
            "the user, wait for explicit approval, then call again with "
            "confirmed=true."
        )
    try:
        preferences = parse_preferences_yaml(preferences_yaml)
        path = save_job_preferences(
            normalized,
            preferences,
            merge=not replace_all,
        )
        saved = load_job_preferences(normalized)
        body = format_preferences_for_prompt(saved)
        mode = "replaced" if replace_all else "merged and saved"
        return (
            f"Job preferences {mode} at {path}.\n\n"
            f"```yaml\n{body}\n```"
        )
    except ValueError as exc:
        return f"Cannot save job preferences: {exc}"
    except Exception as exc:
        return f"Failed to save job preferences: {exc}"
