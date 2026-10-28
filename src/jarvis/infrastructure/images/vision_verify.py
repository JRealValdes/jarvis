"""One vision check per user turn for a web-image candidate.

The chat model still writes the reply. This helper only decides whether the
best image URL may be shown. It uses the same vision-capable chat model as
user-attached images (GPT-4o mini) and a single image URL block.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import resolve_openai_chat_model_id

logger = logging.getLogger(__name__)

class _VisionBudget:
    """Mutable counter shared across LangChain's copied tool context."""

    def __init__(self) -> None:
        self.used = 0


MAX_VISION_CHECKS_PER_TURN: int = 1
# Tool calls run inside ``copy_context()``. Replacing this variable inside
# the tool would not be visible to the next call, so the turn stores one
# mutable counter and the tool updates that object in place.
_budget: ContextVar[_VisionBudget | None] = ContextVar(
    "jarvis_vision_image_checks", default=None
)


def reset_vision_check_budget() -> None:
    """Allow one vision image check for the user turn that is about to run."""
    _budget.set(_VisionBudget())


def vision_checks_used() -> int:
    """Return how many vision image checks this turn has already started."""
    budget = _budget.get()
    if budget is None:
        return 0
    return budget.used


def reserve_vision_check() -> bool:
    """
    Reserve the single vision check for this turn.

    Returns:
        True when this call may contact the vision model. False when the
        turn already used its check.
    """
    budget = _budget.get()
    if budget is None:
        budget = _VisionBudget()
        _budget.set(budget)
    if budget.used >= MAX_VISION_CHECKS_PER_TURN:
        return False
    budget.used += 1
    return True


def _reply_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return " ".join(parts).strip()
    return str(content).strip()


def image_matches_subject(query: str, image_url: str) -> bool:
    """
    Ask a vision model whether ``image_url`` depicts ``query``.

    The caller must :func:`reserve_vision_check` first so a turn cannot
    look at more than one image.

    Args:
        query: What the image was searched for.
        image_url: Direct http(s) image URL.

    Returns:
        True only when the model reply starts with YES. Failures count as NO.
    """
    llm = ChatOpenAI(
        model=resolve_openai_chat_model_id(ModelEnum.GPT_4O_MINI),
        temperature=0,
        max_tokens=8,
    )
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    f"Query: {query}\n"
                    "Does this image clearly depict that subject? "
                    "Reply with exactly YES or NO."
                ),
            },
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    )
    try:
        reply = llm.invoke([message])
    except Exception:
        logger.warning(
            "Vision image check failed for query=%r", query, exc_info=True
        )
        return False
    return _reply_text(reply.content).upper().startswith("YES")
