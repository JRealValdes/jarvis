"""Vision image check: one look per turn, YES/NO parsing, no live API."""

from langchain_core.messages import HumanMessage

from jarvis.infrastructure.images.vision_verify import (
    image_matches_subject,
    reserve_vision_check,
    reset_vision_check_budget,
)


class _Reply:
    def __init__(self, content: str) -> None:
        self.content = content


def test_reserve_allows_one_check_per_turn():
    reset_vision_check_budget()
    assert reserve_vision_check() is True
    assert reserve_vision_check() is False
    reset_vision_check_budget()
    assert reserve_vision_check() is True


def test_yes_sends_the_image_url(monkeypatch):
    seen: list[list] = []

    class _LLM:
        def invoke(self, messages: list) -> _Reply:
            seen.append(messages)
            return _Reply("YES")

    monkeypatch.setattr(
        "jarvis.infrastructure.images.vision_verify.ChatOpenAI",
        lambda **kwargs: _LLM(),
    )
    assert image_matches_subject("a red boat", "https://cdn.example/boat.jpg") is True
    human = seen[0][0]
    assert isinstance(human, HumanMessage)
    assert human.content[1]["image_url"]["url"] == "https://cdn.example/boat.jpg"


def test_no_and_errors_do_not_accept_the_image(monkeypatch):
    class _LLM:
        def invoke(self, messages: list) -> _Reply:
            return _Reply("NO")

    monkeypatch.setattr(
        "jarvis.infrastructure.images.vision_verify.ChatOpenAI",
        lambda **kwargs: _LLM(),
    )
    assert image_matches_subject("a red boat", "https://cdn.example/boat.jpg") is False

    class _Boom:
        def invoke(self, messages: list) -> _Reply:
            raise TimeoutError("slow")

    monkeypatch.setattr(
        "jarvis.infrastructure.images.vision_verify.ChatOpenAI",
        lambda **kwargs: _Boom(),
    )
    assert image_matches_subject("a red boat", "https://cdn.example/boat.jpg") is False
