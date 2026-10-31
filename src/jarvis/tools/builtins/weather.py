"""LangChain tool for structured weather briefs via Open-Meteo."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from jarvis.infrastructure.weather.open_meteo import (
    DEFAULT_FORECAST_DAYS,
    WeatherError,
    lookup_weather,
)

logger = logging.getLogger(__name__)


@tool
def weather_tool(
    location: str = "",
    forecast_days: int = DEFAULT_FORECAST_DAYS,
) -> str:
    """
    Look up current conditions and a short-range forecast for a place.

    Use this for weather questions (temperature, rain, wind, today/tomorrow,
    or a few-day outlook). Do not use web_search_tool for ordinary weather
    forecasts. Prefer a specific city/town; append country or region when the
    name is common (e.g. ``Madrid, Spain``).

    If the location is missing or several places match, the tool returns a
    clarify prompt—ask the user before answering. Present results as short
    bullets (conditions, temperature, precipitation, wind), not long prose.

    Pair with current_date_time_tool when the user says "today" / "tomorrow"
    relative to "now".

    Parameters:
    - location: city or town (optionally ``City, Country`` / ``City, Region``)
    - forecast_days: daily rows to include (default 1 = today + current;
      use 2 for tomorrow as well; max 7)
    """
    try:
        return lookup_weather(location, forecast_days=forecast_days)
    except WeatherError as exc:
        logger.warning("weather_tool provider failure: %s", exc)
        return (
            f"Weather lookup failed: {exc}. Tell the user the weather service "
            "is unavailable and they can retry. Do not invent a forecast."
        )
    except Exception as exc:
        logger.warning("weather_tool failed: %s", exc, exc_info=exc)
        return (
            f"Weather lookup failed ({type(exc).__name__}: {exc}). "
            "Tell the user the lookup failed and they can retry. "
            "Do not invent a forecast."
        )
