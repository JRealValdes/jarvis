"""Built-in LangChain tools shipped with Jarvis.

Register a new tool by defining it in this package and appending it to
``BUILTIN_TOOLS``. The list is explicit so a missing tool is a code change,
not a silent import-time miss.
"""

from langchain_core.tools import BaseTool

from jarvis.tools.builtins.calc import calculate_tool
from jarvis.tools.builtins.date_time import current_date_time_tool
from jarvis.tools.builtins.google_calendar import (
    create_calendar_event_tool,
    delete_calendar_event_tool,
    get_upcoming_events_tool,
)
from jarvis.tools.builtins.job_preferences import (
    save_job_preferences_tool,
    show_job_preferences_tool,
)
from jarvis.tools.builtins.linkedin_reply import draft_linkedin_reply_tool
from jarvis.tools.builtins.linkedin_reply_examples import (
    add_linkedin_reply_example_tool,
    show_linkedin_reply_examples_tool,
)
from jarvis.tools.builtins.speech_to_text import speech_to_text_tool
from jarvis.tools.builtins.web_search import web_search_tool

BUILTIN_TOOLS: list[BaseTool] = [
    calculate_tool,
    current_date_time_tool,
    get_upcoming_events_tool,
    create_calendar_event_tool,
    delete_calendar_event_tool,
    show_job_preferences_tool,
    save_job_preferences_tool,
    draft_linkedin_reply_tool,
    show_linkedin_reply_examples_tool,
    add_linkedin_reply_example_tool,
    speech_to_text_tool,
    web_search_tool,
]
