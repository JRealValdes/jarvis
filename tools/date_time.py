from langchain.tools import tool
from datetime import datetime

@tool
def current_date_time_tool():
    """
    Returns the current date and time with second-level precision, including the day of the week.
    """
    now = datetime.now()
    weekday = now.strftime("%A")
    formatted = now.strftime("%Y-%m-%d %H:%M:%S")
    return f"Hoy es {weekday}, y la fecha y hora actual es: {formatted}"
