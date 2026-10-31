"""Weather lookup via the free Open-Meteo geocoding and forecast APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_LOCATION_CANDIDATES = 5
HARD_MAX_FORECAST_DAYS = 7
DEFAULT_FORECAST_DAYS = 1
USER_AGENT = "JarvisWeather/1.0 (+https://github.com/JRealValdes/jarvis)"

# WMO Weather interpretation codes (WW) used by Open-Meteo.
_WMO_WEATHER: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snow fall", "🌨️"),
    73: ("Moderate snow fall", "🌨️"),
    75: ("Heavy snow fall", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "🌧️"),
    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


class WeatherError(Exception):
    """Open-Meteo request or response failed."""


@dataclass(frozen=True)
class GeoLocation:
    """A geocoded place from Open-Meteo."""

    name: str
    latitude: float
    longitude: float
    country: str
    admin1: str
    timezone: str
    population: int | None = None

    def display_name(self) -> str:
        """Return a short human-readable place label."""
        parts = [self.name]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


def clamp_forecast_days(forecast_days: int) -> int:
    """Clamp ``forecast_days`` to ``1..HARD_MAX_FORECAST_DAYS``."""
    if forecast_days < 1:
        return 1
    if forecast_days > HARD_MAX_FORECAST_DAYS:
        return HARD_MAX_FORECAST_DAYS
    return forecast_days


def describe_weather_code(code: int | None) -> str:
    """
    Map a WMO weather code to an English label with an optional emoji.

    Args:
        code: WMO WW code from Open-Meteo, or None when missing.

    Returns:
        Label such as ``Partly cloudy ⛅``, or ``Unknown`` when unmapped.
    """
    if code is None:
        return "Unknown"
    try:
        key = int(code)
    except (TypeError, ValueError):
        return "Unknown"
    label, emoji = _WMO_WEATHER.get(key, (f"Weather code {key}", ""))
    return f"{label} {emoji}".strip()


def _http_get(
    url: str,
    params: dict[str, Any],
    *,
    timeout_seconds: float,
    get_fn: Callable[..., Any] | None,
) -> dict[str, Any]:
    """GET JSON from Open-Meteo and raise ``WeatherError`` on failure."""
    http_get = get_fn or requests.get
    try:
        response = http_get(
            url,
            params=params,
            timeout=timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise WeatherError(f"Open-Meteo request failed: {exc}") from exc
    except ValueError as exc:
        raise WeatherError(f"Open-Meteo returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise WeatherError("Open-Meteo returned a non-object JSON payload.")
    return payload


def search_locations(
    name: str,
    *,
    count: int = DEFAULT_LOCATION_CANDIDATES,
    language: str = "en",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    get_fn: Callable[..., Any] | None = None,
) -> list[GeoLocation]:
    """
    Resolve a place name to candidate coordinates via Open-Meteo geocoding.

    Args:
        name: City, town, or place (optionally ``City, Country``).
        count: Maximum candidates to return (1–10).
        language: Preferred language for place names.
        timeout_seconds: HTTP timeout.
        get_fn: Optional injectable GET (tests).

    Returns:
        Matching locations, possibly empty.

    Raises:
        WeatherError: On transport or API failures.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return []
    limit = max(1, min(int(count), 10))
    payload = _http_get(
        GEOCODING_URL,
        {
            "name": cleaned,
            "count": limit,
            "language": language,
            "format": "json",
        },
        timeout_seconds=timeout_seconds,
        get_fn=get_fn,
    )
    raw_results = payload.get("results") or []
    locations: list[GeoLocation] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            locations.append(
                GeoLocation(
                    name=str(item.get("name") or cleaned),
                    latitude=float(item["latitude"]),
                    longitude=float(item["longitude"]),
                    country=str(item.get("country") or ""),
                    admin1=str(item.get("admin1") or ""),
                    timezone=str(item.get("timezone") or "auto"),
                    population=(
                        int(item["population"])
                        if item.get("population") is not None
                        else None
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping malformed geocoding hit: %s (%s)", item, exc)
    return locations


def fetch_forecast(
    latitude: float,
    longitude: float,
    *,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    timezone: str = "auto",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    get_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """
    Fetch current conditions and a short daily forecast from Open-Meteo.

    Args:
        latitude: WGS84 latitude.
        longitude: WGS84 longitude.
        forecast_days: Number of daily rows (clamped to 1–7).
        timezone: IANA timezone or ``auto``.
        timeout_seconds: HTTP timeout.
        get_fn: Optional injectable GET (tests).

    Returns:
        Parsed Open-Meteo forecast JSON object.

    Raises:
        WeatherError: On transport or API failures.
    """
    days = clamp_forecast_days(forecast_days)
    return _http_get(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone or "auto",
            "forecast_days": days,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,weather_code,wind_speed_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max,"
                "wind_speed_10m_max"
            ),
        },
        timeout_seconds=timeout_seconds,
        get_fn=get_fn,
    )


def _place_name_from_query(query: str) -> str:
    """Return the place token before an optional ``, country/region`` qualifier."""
    return query.split(",", 1)[0].strip()


def pick_location_candidates(
    query: str,
    locations: list[GeoLocation],
) -> list[GeoLocation]:
    """
    Narrow geocoding hits to the place the user likely meant.

    Prefers an exact (case-insensitive) match on the name before a comma so
    ``Madrid, Spain`` does not stay ambiguous with prefix hits like
    ``Madridejos``. When several exact names remain (e.g. plain ``Madrid``),
    all of them are returned for clarification.

    Args:
        query: Original location string.
        locations: Raw geocoding hits.

    Returns:
        One or more candidates; empty when ``locations`` is empty.
    """
    if not locations:
        return []
    place_name = _place_name_from_query(query)
    if not place_name:
        return list(locations)
    exact = [
        place
        for place in locations
        if place.name.casefold() == place_name.casefold()
    ]
    return exact if exact else list(locations)


def format_ambiguous_locations(query: str, locations: list[GeoLocation]) -> str:
    """
    Format several geocoding hits so the agent can ask the user to choose.

    Args:
        query: Original location string from the user/tool call.
        locations: Candidate places.

    Returns:
        English instruction listing numbered candidates.
    """
    lines = [
        f"Ambiguous location for '{query}'. Ask the user which place they mean "
        "before answering. Candidates:",
    ]
    for index, place in enumerate(locations, start=1):
        pop = (
            f" · pop. {place.population:,}"
            if place.population is not None
            else ""
        )
        lines.append(f"{index}. {place.display_name()}{pop}")
    lines.append(
        "When they clarify, call weather_tool again with a more specific "
        "location (e.g. 'City, Country')."
    )
    return "\n".join(lines)


def _fmt_num(value: Any, digits: int = 1) -> str:
    """Format a numeric API value, or ``n/a`` when missing."""
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if number.is_integer():
        return str(int(number))
    return f"{number:.{digits}f}"


def format_weather_brief(
    location: GeoLocation,
    forecast: dict[str, Any],
    *,
    forecast_days: int,
) -> str:
    """
    Format current + daily forecast as short English bullet sections.

    Args:
        location: Resolved place.
        forecast: Open-Meteo forecast payload.
        forecast_days: How many daily rows were requested (after clamp).

    Returns:
        Markdown-ish brief suitable for the agent to present as bullets.
    """
    days = clamp_forecast_days(forecast_days)
    current = forecast.get("current") or {}
    current_units = forecast.get("current_units") or {}
    daily = forecast.get("daily") or {}
    daily_units = forecast.get("daily_units") or {}
    tz = forecast.get("timezone") or location.timezone or "auto"

    temp_u = current_units.get("temperature_2m", "°C")
    precip_u = current_units.get("precipitation", "mm")
    wind_u = current_units.get("wind_speed_10m", "km/h")
    daily_temp_u = daily_units.get("temperature_2m_max", temp_u)
    daily_precip_u = daily_units.get("precipitation_sum", precip_u)
    daily_wind_u = daily_units.get("wind_speed_10m_max", wind_u)

    lines = [
        f"## Weather for {location.display_name()}",
        f"- Timezone: {tz}",
        "- Source: Open-Meteo",
        "",
        "### Current",
        f"- Conditions: {describe_weather_code(current.get('weather_code'))}",
        (
            f"- Temperature: {_fmt_num(current.get('temperature_2m'))} {temp_u}"
            f" (feels like {_fmt_num(current.get('apparent_temperature'))}"
            f" {temp_u})"
        ),
        f"- Humidity: {_fmt_num(current.get('relative_humidity_2m'), 0)}%",
        f"- Precipitation: {_fmt_num(current.get('precipitation'))} {precip_u}",
        f"- Wind: {_fmt_num(current.get('wind_speed_10m'))} {wind_u}",
        "",
        "### Daily forecast",
    ]

    times = list(daily.get("time") or [])
    codes = list(daily.get("weather_code") or [])
    highs = list(daily.get("temperature_2m_max") or [])
    lows = list(daily.get("temperature_2m_min") or [])
    precip = list(daily.get("precipitation_sum") or [])
    precip_prob = list(daily.get("precipitation_probability_max") or [])
    wind_max = list(daily.get("wind_speed_10m_max") or [])

    row_count = min(days, len(times))
    if row_count == 0:
        lines.append("- No daily forecast rows returned.")
    for index in range(row_count):
        day = times[index]
        label = "today" if index == 0 else ("tomorrow" if index == 1 else "")
        day_prefix = f"{day}" + (f" ({label})" if label else "")
        code = codes[index] if index < len(codes) else None
        high = highs[index] if index < len(highs) else None
        low = lows[index] if index < len(lows) else None
        rain = precip[index] if index < len(precip) else None
        chance = precip_prob[index] if index < len(precip_prob) else None
        wind = wind_max[index] if index < len(wind_max) else None
        chance_text = (
            f" ({_fmt_num(chance, 0)}% chance)" if chance is not None else ""
        )
        lines.append(
            f"- {day_prefix}: {describe_weather_code(code)} · "
            f"High {_fmt_num(high)} {daily_temp_u} · "
            f"Low {_fmt_num(low)} {daily_temp_u} · "
            f"Precip {_fmt_num(rain)} {daily_precip_u}{chance_text} · "
            f"Wind max {_fmt_num(wind)} {daily_wind_u}"
        )

    lines.append("")
    lines.append(
        "Present this to the user as short bullets in their language. "
        "Do not expand into long narrative paragraphs."
    )
    return "\n".join(lines)


def lookup_weather(
    location: str,
    *,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    get_fn: Callable[..., Any] | None = None,
) -> str:
    """
    Resolve a place and return a structured weather brief, or a clarify prompt.

    Args:
        location: City/town (add country/region when the name is common).
        forecast_days: Daily rows to include (1 = today, 2 = +tomorrow, …).
        timeout_seconds: HTTP timeout for geocoding and forecast.
        get_fn: Optional injectable GET (tests).

    Returns:
        Structured brief, an ambiguity/not-found message, or an error string.

    Raises:
        WeatherError: Propagated only when callers need it; the tool layer
            usually catches and returns the message.
    """
    cleaned = (location or "").strip()
    if not cleaned:
        return (
            "Location is missing. Ask the user which city or town they want "
            "the weather for (add country or region if the name is ambiguous), "
            "then call weather_tool again."
        )

    days = clamp_forecast_days(forecast_days)
    raw_hits = search_locations(
        cleaned,
        timeout_seconds=timeout_seconds,
        get_fn=get_fn,
    )
    if not raw_hits:
        return (
            f"No places found for '{cleaned}'. Ask the user for a clearer "
            "city/town name (optionally with country or region)."
        )
    candidates = pick_location_candidates(cleaned, raw_hits)
    if len(candidates) > 1:
        return format_ambiguous_locations(cleaned, candidates)

    place = candidates[0]
    forecast = fetch_forecast(
        place.latitude,
        place.longitude,
        forecast_days=days,
        timezone=place.timezone or "auto",
        timeout_seconds=timeout_seconds,
        get_fn=get_fn,
    )
    return format_weather_brief(place, forecast, forecast_days=days)
