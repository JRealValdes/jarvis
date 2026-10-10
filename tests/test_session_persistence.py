"""Checkpoint-backed history and session state (no network)."""

from langchain_core.messages import AIMessage, HumanMessage

from jarvis.agents.checkpointer import open_model_checkpointer
from jarvis.agents.graph import compile_tool_agent
from jarvis.agents.session.cache import get_agents_cache, get_sessions_cache
from jarvis.agents.session.history import get_message_history
from jarvis.agents.session.orchestrator import JarvisSession, _session_for
from jarvis.core.config import LOCAL_THREAD_ID
from jarvis.core.enums import ModelEnum
from jarvis.domain.chat.chat_state import ChatState
from jarvis.domain.users.prompts import get_welcome_message
from jarvis.interfaces.cli import thread_id as cli_thread_id
from jarvis.interfaces.gradio_app import thread_id as ui_thread_id


class _FakeLLM:
    """Chat model stand-in that acknowledges every turn without tools."""

    def bind_tools(self, tools: list) -> "_FakeLLM":
        """Return self so the graph can bind an empty tool list."""
        return self

    def invoke(self, messages: list) -> AIMessage:
        """Return a fixed assistant message."""
        return AIMessage(content="ack")


def _user(real_name: str) -> dict:
    """Minimal user dict for session tests."""
    return {
        "real_name": real_name,
        "jarvis_name": real_name,
        "is_female": False,
        "admin": False,
    }


def _seed_thread(thread_id: str, text: str, real_name: str) -> None:
    """Write one human/assistant turn into the model checkpoint file."""
    opened = open_model_checkpointer(ModelEnum.GPT_4O_MINI)
    try:
        graph, _saver = compile_tool_agent(
            _FakeLLM(), [], checkpointer=opened.saver
        )
        graph.invoke(
            {"messages": [HumanMessage(content=text)], "real_name": real_name},
            {"configurable": {"thread_id": thread_id}},
        )
    finally:
        opened.close()


def test_local_interfaces_share_configured_thread_id():
    assert cli_thread_id == LOCAL_THREAD_ID
    assert ui_thread_id == LOCAL_THREAD_ID


def test_message_history_reads_checkpoint_without_session_cache():
    _seed_thread("ada", "hello", "Ada")
    history = get_message_history("ada", ModelEnum.GPT_4O_MINI)
    assert history[0] == {"role": "user", "content": "hello"}
    assert history[1] == {"role": "assistant", "content": "ack"}


def test_message_history_missing_thread_is_empty():
    assert get_message_history("nobody", ModelEnum.GPT_4O_MINI) == []


def test_message_history_prefers_live_agent_graph():
    _seed_thread("ada", "on-disk", "Ada")

    class _Graph:
        def get_state(self, config: dict) -> object:
            class _Snapshot:
                values = {
                    "messages": [HumanMessage(content="in-memory")],
                    "real_name": "Ada",
                }

            return _Snapshot()

    class _Agent:
        graph = _Graph()
        memory = object()

    cache = get_agents_cache()
    cache[ModelEnum.GPT_4O_MINI] = _Agent()
    try:
        history = get_message_history("ada", ModelEnum.GPT_4O_MINI)
        assert history == [{"role": "user", "content": "in-memory"}]
    finally:
        cache.pop(ModelEnum.GPT_4O_MINI, None)


def test_existing_checkpoint_skips_rewelcome():
    _seed_thread("ada", "hello", "Ada")
    user = _user("Ada")
    session = JarvisSession(ModelEnum.GPT_4O_MINI, "ada", user_info=user)
    assert session._chat_state == ChatState.INITIALIZED
    assert session._direct_reply("status") is None
    messages = session._messages_for_model("status")
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "status"


def test_new_authenticated_session_still_welcomes():
    user = _user("Ada")
    session = JarvisSession(ModelEnum.GPT_4O_MINI, "new-ada", user_info=user)
    assert session._chat_state == ChatState.NOT_INITIALIZED
    assert session._direct_reply("hello") == [get_welcome_message(user)]


def test_checkpoint_restores_user_when_caller_is_anonymous(monkeypatch):
    _seed_thread("ada", "hello", "Ada")
    monkeypatch.setattr(
        "jarvis.agents.session.orchestrator.get_user_by_field",
        lambda field, value, is_sensitive=False: _user(value),
    )
    session = JarvisSession(ModelEnum.GPT_4O_MINI, "ada")
    assert session.valid_user is True
    assert session.user["real_name"] == "Ada"
    assert session._chat_state == ChatState.INITIALIZED


def test_checkpoint_without_user_row_stays_initialized(monkeypatch):
    _seed_thread("ghost", "hello", "Ghost")
    monkeypatch.setattr(
        "jarvis.agents.session.orchestrator.get_user_by_field",
        lambda field, value, is_sensitive=False: None,
    )
    session = JarvisSession(ModelEnum.GPT_4O_MINI, "ghost")
    assert session._chat_state == ChatState.INITIALIZED
    assert session.valid_user is False


def test_session_cache_refreshes_authenticated_user():
    cache = get_sessions_cache()
    thread_id = "refresh-thread"
    key = (ModelEnum.GPT_4O_MINI, thread_id)
    cache.pop(key, None)
    try:
        anonymous = _session_for(ModelEnum.GPT_4O_MINI, thread_id, None)
        assert anonymous.valid_user is False
        authenticated = _session_for(
            ModelEnum.GPT_4O_MINI, thread_id, _user("Ada")
        )
        assert authenticated is anonymous
        assert authenticated.user["real_name"] == "Ada"
        assert authenticated.valid_user is True
        switched = _session_for(ModelEnum.GPT_4O_MINI, thread_id, _user("Grace"))
        assert switched.user["real_name"] == "Grace"
        still = _session_for(ModelEnum.GPT_4O_MINI, thread_id, None)
        assert still.user["real_name"] == "Grace"
        assert still.valid_user is True
    finally:
        cache.pop(key, None)
