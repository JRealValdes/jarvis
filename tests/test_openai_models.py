"""Unit tests for OpenAI model id mapping (no network)."""

from typing import cast

import pytest

from jarvis.core.enums import ModelEnum
from jarvis.core.openai_models import (
    is_openai_chat_model,
    resolve_openai_chat_model_id,
)


def test_resolve_gpt_4o_mini_id():
    assert resolve_openai_chat_model_id(ModelEnum.GPT_4O_MINI) == "gpt-4o-mini"


def test_resolve_gpt_3_5_id():
    assert resolve_openai_chat_model_id(ModelEnum.GPT_3_5) == "gpt-3.5-turbo"


def test_resolve_rejects_unknown_model():
    with pytest.raises(ValueError, match="Unsupported OpenAI chat model"):
        resolve_openai_chat_model_id(cast(ModelEnum, "not-a-model"))


def test_is_openai_chat_model():
    assert is_openai_chat_model(ModelEnum.GPT_4O_MINI) is True
    assert is_openai_chat_model(ModelEnum.GPT_3_5) is True
