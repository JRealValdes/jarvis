import datetime
from langchain_core.tools import tool
from googleapiclient.discovery import build
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState
from typing import Optional

from api.google_api.jarvis_google_authentication import get_authentications_for_user

@tool
def get_upcoming_events_tool(
    real_name: Annotated[str, InjectedState("real_name")],
    num_events: int = 10
) -> str:
    """
    Get the next upcoming events from the user's Google Calendar.
    The parameter real_name is the real_name defined for the user.
    The number of events to return can be specified with num_events.
    """
    real_name = real_name.strip().lower()
    authentications = get_authentications_for_user(real_name, allow_logging_popup=True)
    events = []
    for authentication in authentications.values():
        service = build("calendar", "v3", credentials=authentication)
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=num_events,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events.extend(events_result.get("items", []))

    if not events:
        return "No upcoming events found."
    
    events = sorted(events,key=lambda event: event["start"].get('dateTime', event["start"].get('date')), reverse=False)
    events = events[:num_events] if len(events) > num_events else events

    result = ""
    for event in events:
        result += f"{event['start'].get('dateTime', event['start'].get('date'))} - {event['summary']}\n"

    return result.strip()


@tool
def create_calendar_event_tool(
    real_name: Annotated[str, InjectedState("real_name")],
    start_datetime: str,
    end_datetime: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: str = "Europe/Madrid"
) -> str:
    """
    Create a new event in the user's Google Calendar.

    Required:
    - start_datetime: Start date and time in ISO 8601 format (e.g. '2025-07-08T09:00:00')
    - end_datetime: End date and time in ISO 8601 format (e.g. '2025-07-08T10:00:00')

    Optional:
    - title: Event title
    - description: Event description
    - location: Event location
    - timezone: Timezone of the event (default is 'Europe/Madrid')
    """
    try:
        real_name = real_name.strip().lower()
        authentications = get_authentications_for_user(real_name, allow_logging_popup=True)
        if not authentications:
            return "No authentication found for the user."

        authentication = list(authentications.values())[0]
        service = build("calendar", "v3", credentials=authentication)

        event = {
            "start": {
                "dateTime": start_datetime,
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_datetime,
                "timeZone": timezone,
            },
            "reminders": {
                "useDefault": True
            },
        }

        if title and title.strip():
            event["summary"] = title.strip()
        if description and description.strip():
            event["description"] = description.strip()
        if location and location.strip():
            event["location"] = location.strip()

        created_event = service.events().insert(calendarId="primary", body=event).execute()
        return f"Evento creado correctamente: {created_event.get('htmlLink')}"

    except Exception as e:
        return f"Error al crear el evento: {str(e)}"
