"""Seed assistant message into a task chat thread."""

from jarvis.agents.session.history import get_message_history
from jarvis.agents.session.seed import seed_assistant_message
from jarvis.core.enums import ModelEnum


def test_seed_assistant_message_writes_history():
    thread_id = "task:seed-test-thread"
    seed_assistant_message(
        thread_id,
        "Morning digest: all quiet.",
        real_name="Alice",
        model=ModelEnum.GPT_4O_MINI,
        reset_first=True,
    )
    history = get_message_history(thread_id, ModelEnum.GPT_4O_MINI)
    assert history == [
        {"role": "assistant", "content": "Morning digest: all quiet."}
    ]
