"""Map ModelEnum members to OpenAI Chat Completions model ids."""

from jarvis.core.enums import ModelEnum

_OPENAI_CHAT_MODEL_IDS: dict[ModelEnum, str] = {
    ModelEnum.GPT_3_5: "gpt-3.5-turbo",
    ModelEnum.GPT_4O_MINI: "gpt-4o-mini",
}


def resolve_openai_chat_model_id(model: ModelEnum) -> str:
    """
    Return the OpenAI API model id for a Jarvis ModelEnum member.

    Args:
        model: Supported OpenAI-backed ModelEnum value.

    Returns:
        Model id string for ChatOpenAI / the OpenAI API.

    Raises:
        ValueError: If ``model`` is not an OpenAI chat model.
    """
    try:
        return _OPENAI_CHAT_MODEL_IDS[model]
    except KeyError as exc:
        raise ValueError(f"Unsupported OpenAI chat model: {model}") from exc


def is_openai_chat_model(model: ModelEnum) -> bool:
    """Return True if ``model`` is backed by OpenAI Chat Completions."""
    return model in _OPENAI_CHAT_MODEL_IDS
