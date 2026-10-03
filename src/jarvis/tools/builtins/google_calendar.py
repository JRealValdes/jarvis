"""LangChain tools to read and modify Google Calendar per user."""

import datetime
from langchain_core.tools import tool
from googleapiclient.discovery import build
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState
from typing import Optional
from dateutil import parser

from jarvis.infrastructure.google.calendar_auth import get_authentications_for_user


def ensure_timezone(dt_string: str, fallback_tz: str = "+00:00") -> str:
    """
    Normalize an ISO 8601 datetime by adding a timezone if missing.

    Args:
        dt_string: Date/time in ISO format.
        fallback_tz: Timezone suffix if absent (e.g. ``+00:00``).

    Returns:
        ISO string with timezone.

    Raises:
        ValueError: If the format is not parseable.
    """
    try:
        dt = parser.isoparse(dt_string)
        if dt.tzinfo is None:
            return dt.isoformat() + fallback_tz
        return dt.isoformat()
    except Exception:
        raise ValueError(
            f"Invalid date format: '{dt_string}'. Use ISO 8601 "
            "(e.g. 2025-07-22T00:00:00+02:00)"
        )


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
    - num_events: optional maximum number of events to return
    - date_from: optional ISO8601 start datetime (e.g. "2025-07-10T00:00:00+02:00"). If left empty, defaults to now.
    - date_to: optional ISO8601 end datetime (e.g. "2025-07-11T00:00:00+02:00"). If left empty, defaults to no end date.

    If no date range is specified, it defaults to now → future.
    """
    try:
        real_name = real_name.strip().lower()
        authentications = get_authentications_for_user(real_name, allow_logging_popup=True)

        if not authentications:
            return "No credentials found to access the calendar."

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
                return f"Error querying one of the calendars: {str(e)}"

        if not events:
            return "No events found for the given dates."

        events = sorted(
            events,
            key=lambda event: event["start"].get("dateTime", event["start"].get("date")),
            reverse=False,
        )
        events = events[:num_events] if len(events) > num_events else events

        result = (
            "This is the result of the events query.\n\n"
            "📌 Note for you, agent: the 'Event ID' field is useful for internal handling, "
            "but should normally not be shown to the user unless they explicitly ask.\n\n"
            "🔍 Review the following list carefully. It may contain the information you need "
            "to answer the user's request correctly.\n\n"
            "📋 Format:\n'Start date and time - Event title - Event ID'\n\n"
        )

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "Untitled")
            event_id = event.get("id", "No ID")
            result += f"{start} - {summary} - {event_id}\n"

        return result.strip()

    except FileNotFoundError as fnf:
        return (
            f"FileNotFoundError. Authentication directory not found for user "
            f"'{real_name}'. Path checked: {fnf.filename}"
        )
    except ValueError as ve:
        return f"ValueError: {str(ve)}"
    except Exception as e:
        return f"Unknown error. Could not retrieve events: {str(e)}"


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
        return (
            f"Event created successfully. Link: {created_event.get('htmlLink')}. "
            f"ID: {created_event.get('id')}"
        )

    except Exception as e:
        return f"Error creating event: {str(e)}"


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
        return f"Event with ID '{event_id}' deleted successfully."

    except Exception as e:
        return f"Could not delete event with ID '{event_id}': {str(e)}"
