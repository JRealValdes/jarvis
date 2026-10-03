"""Current date and time tool for the agent."""

from datetime import datetime

from langchain_core.tools import tool


@tool
def current_date_time_tool() -> str:
    """
    Return the current date and time with weekday.

    Returns:
        English string with weekday and timestamp ``YYYY-MM-DD HH:MM:SS``.
    """
    now = datetime.now()
    weekday = now.strftime("%A")
    formatted = now.strftime("%Y-%m-%d %H:%M:%S")
    return f"Today is {weekday}, and the current date and time is: {formatted}"
