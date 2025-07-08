import datetime
from langchain_core.tools import tool
from googleapiclient.discovery import build
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState
from typing import Optional
from dateutil import parser

from api.google_api.jarvis_google_authentication import get_authentications_for_user


def ensure_timezone(dt_string: str, fallback_tz: str = "+00:00") -> str:
    try:
        dt = parser.isoparse(dt_string)
        if dt.tzinfo is None:
            return dt.isoformat() + fallback_tz
        return dt.isoformat()
    except Exception:
        raise ValueError(f"Formato de fecha inválido: '{dt_string}'. Usa ISO 8601 (e.g. 2025-07-22T00:00:00+02:00)")


@tool
def get_upcoming_events_tool(
    real_name: Annotated[str, InjectedState("real_name")],
    num_events: int = 50,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Get upcoming events from the user's Google Calendar, optionally filtered by date range.

    Parameters:
    - real_name: user identifier
    - num_events: maximum number of events to return
    - date_from: optional ISO8601 start datetime (e.g. "2025-07-10T00:00:00+02:00"). If left empty, defaults to now.
    - date_to: optional ISO8601 end datetime (e.g. "2025-07-11T00:00:00+02:00"). If left empty, defaults to no end date.

    If no date range is specified, it defaults to now → future.
    """
    try:
        real_name = real_name.strip().lower()
        authentications = get_authentications_for_user(real_name, allow_logging_popup=True)

        if not authentications:
            return "No se encontraron credenciales para acceder al calendario."

        time_min = ensure_timezone(date_from) if date_from else datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        time_max = ensure_timezone(date_to) if date_to else None

        events = []

        for authentication in authentications.values():
            try:
                service = build("calendar", "v3", credentials=authentication)

                list_kwargs = {
                    "calendarId": "primary",
                    "timeMin": time_min,
                    "maxResults": num_events,
                    "singleEvents": True,
                    "orderBy": "startTime",
                }
                if time_max:
                    list_kwargs["timeMax"] = time_max

                events_result = service.events().list(**list_kwargs).execute()
                events.extend(events_result.get("items", []))

            except Exception as e:
                return f"Error al consultar uno de los calendarios: {str(e)}"

        if not events:
            return "No se encontraron eventos para las fechas indicadas."

        events = sorted(
            events,
            key=lambda event: event["start"].get("dateTime", event["start"].get("date")),
            reverse=False,
        )
        events = events[:num_events] if len(events) > num_events else events

        result = ""
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "Sin título")
            event_id = event.get("id", "Sin ID")
            result += f"{start} - {summary} - {event_id}\n"

        return result.strip()

    except ValueError as ve:
        return str(ve)
    except Exception as e:
        return f"No fue posible obtener los eventos: {str(e)}"


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

    Returns a confirmation message with the event link and ID if successful.
    If an error occurs, it returns an error message.
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
        return f"Evento creado correctamente. Link: {created_event.get('htmlLink')}. ID: {created_event.get('id')}"

    except Exception as e:
        return f"Error al crear el evento: {str(e)}"


@tool
def delete_calendar_event_tool(
    real_name: Annotated[str, InjectedState("real_name")],
    event_id: str
) -> str:
    """
    Delete an event from the user's Google Calendar by its event ID.

    Required:
    - event_id: The ID of the event to delete (must be exact)
    """
    try:
        real_name = real_name.strip().lower()
        authentications = get_authentications_for_user(real_name, allow_logging_popup=True)
        if not authentications:
            return "No authentication found for the user."

        authentication = list(authentications.values())[0]
        service = build("calendar", "v3", credentials=authentication)

        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"Evento con ID '{event_id}' eliminado correctamente."

    except Exception as e:
        return f"No se pudo eliminar el evento con ID '{event_id}': {str(e)}"
