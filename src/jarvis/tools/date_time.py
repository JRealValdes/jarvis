"""Current date and time tool for the agent."""

from datetime import datetime

from langchain_core.tools import tool


@tool
def current_date_time_tool() -> str:
    """
    Devuelve la fecha y hora actuales con día de la semana.

    Args:
        Ninguno.

    Returns:
        Cadena en español con día de la semana y timestamp ``YYYY-MM-DD HH:MM:SS``.
    """
    now = datetime.now()
    weekday = now.strftime("%A")
    formatted = now.strftime("%Y-%m-%d %H:%M:%S")
    return f"Hoy es {weekday}, y la fecha y hora actual es: {formatted}"
