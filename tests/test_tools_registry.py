"""Explicit built-in tool registry."""

import importlib
import inspect
import pkgutil

from jarvis.tools import local_tools
from jarvis.tools.builtins import BUILTIN_TOOLS


def test_local_tools_follow_the_declared_list():
    assert local_tools == list(BUILTIN_TOOLS)
    assert [tool.name for tool in local_tools] == [
        "calculate_tool",
        "current_date_time_tool",
        "get_upcoming_events_tool",
        "create_calendar_event_tool",
        "delete_calendar_event_tool",
        "show_job_preferences_tool",
        "save_job_preferences_tool",
        "draft_linkedin_reply_tool",
        "show_linkedin_reply_examples_tool",
        "add_linkedin_reply_example_tool",
        "transcribe_audio",
        "web_image_search_tool",
        "web_search_tool",
    ]


def test_declared_list_includes_every_builtin_tool():
    discovered = []
    package = importlib.import_module("jarvis.tools.builtins")
    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
        if is_pkg or module_name.startswith("_"):
            continue
        module = importlib.import_module(f"jarvis.tools.builtins.{module_name}")
        for name, obj in inspect.getmembers(module):
            if name.endswith("_tool"):
                discovered.append(obj)
    assert {id(tool) for tool in discovered} == {id(tool) for tool in BUILTIN_TOOLS}
