"""Open-Meteo weather client and weather_tool tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import requests

from jarvis.infrastructure.weather.open_meteo import (
    GeoLocation,
    WeatherError,
    clamp_forecast_days,
    describe_weather_code,
    fetch_forecast,
    format_ambiguous_locations,
    format_weather_brief,
    lookup_weather,
    pick_location_candidates,
    search_locations,
)
from jarvis.tools.builtins.weather import weather_tool


def _json_response(payload: dict[str, Any], status_code: int = 200) -> SimpleNamespace:
    """Build a minimal response object like ``requests.Response``."""

    def raise_for_status() -> None:
        if status_code >= 400:
            raise requests.HTTPError(f"status {status_code}")

    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload,
        raise_for_status=raise_for_status,
    )


MADRID = GeoLocation(
    name="Madrid",
    latitude=40.4165,
    longitude=-3.70256,
    country="Spain",
    admin1="Madrid",
    timezone="Europe/Madrid",
    population=3255944,
)

FORECAST_PAYLOAD = {
    "timezone": "Europe/Madrid",
    "current_units": {
        "temperature_2m": "°C",
        "precipitation": "mm",
        "wind_speed_10m": "km/h",
    },
    "current": {
        "temperature_2m": 18.8,
        "apparent_temperature": 18.4,
        "relative_humidity_2m": 52,
        "precipitation": 0.0,
        "weather_code": 0,
        "wind_speed_10m": 1.8,
    },
    "daily_units": {
        "temperature_2m_max": "°C",
        "precipitation_sum": "mm",
        "wind_speed_10m_max": "km/h",
        "precipitation_probability_max": "%",
    },
    "daily": {
        "time": ["2026-10-31", "2026-11-01"],
        "weather_code": [2, 45],
        "temperature_2m_max": [20.8, 20.0],
        "temperature_2m_min": [8.6, 8.9],
        "precipitation_sum": [0.0, 0.0],
        "precipitation_probability_max": [0, 10],
        "wind_speed_10m_max": [6.2, 7.9],
    },
}


def test_clamp_forecast_days():
    assert clamp_forecast_days(0) == 1
    assert clamp_forecast_days(3) == 3
    assert clamp_forecast_days(99) == 7


def test_describe_weather_code():
    assert "Clear sky" in describe_weather_code(0)
    assert "Partly cloudy" in describe_weather_code(2)
    assert "Unknown" == describe_weather_code(None)
    assert "Weather code 123" in describe_weather_code(123)


def test_search_locations_parses_results():
    payload = {
        "results": [
            {
                "name": "Madrid",
                "latitude": 40.4165,
                "longitude": -3.70256,
                "country": "Spain",
                "admin1": "Madrid",
                "timezone": "Europe/Madrid",
                "population": 3255944,
            }
        ]
    }
    hits = search_locations(
        "Madrid, Spain",
        get_fn=lambda *a, **k: _json_response(payload),
    )
    assert len(hits) == 1
    assert hits[0].name == "Madrid"
    assert hits[0].country == "Spain"
    assert hits[0].display_name() == "Madrid, Spain"


def test_search_locations_empty_name():
    assert search_locations("") == []
    assert search_locations("   ") == []


def test_fetch_forecast_requests_expected_params():
    captured: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> SimpleNamespace:
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return _json_response(FORECAST_PAYLOAD)

    data = fetch_forecast(40.4, -3.7, forecast_days=2, get_fn=fake_get)
    assert data["timezone"] == "Europe/Madrid"
    assert "forecast" in captured["url"]
    assert captured["params"]["forecast_days"] == 2
    assert "temperature_2m" in captured["params"]["current"]


def test_format_ambiguous_locations_lists_candidates():
    other = GeoLocation(
        name="Madrid",
        latitude=4.7,
        longitude=-74.2,
        country="Colombia",
        admin1="Cundinamarca",
        timezone="America/Bogota",
        population=135000,
    )
    text = format_ambiguous_locations("Madrid", [MADRID, other])
    assert "Ambiguous location" in text
    assert "Spain" in text
    assert "Colombia" in text
    assert "weather_tool again" in text


def test_format_weather_brief_includes_current_and_daily():
    text = format_weather_brief(MADRID, FORECAST_PAYLOAD, forecast_days=2)
    assert "Weather for Madrid, Spain" in text
    assert "### Current" in text
    assert "Clear sky" in text
    assert "18.8" in text
    assert "### Daily forecast" in text
    assert "today" in text
    assert "tomorrow" in text
    assert "Partly cloudy" in text
    assert "Fog" in text
    assert "short bullets" in text


def test_lookup_weather_missing_location():
    text = lookup_weather("")
    assert "Location is missing" in text
    assert "Ask the user" in text


def test_lookup_weather_not_found():
    text = lookup_weather(
        "Zzznothereville",
        get_fn=lambda *a, **k: _json_response({"results": []}),
    )
    assert "No places found" in text


def test_pick_location_candidates_prefers_exact_name():
    prefix_noise = GeoLocation(
        name="Madridejos",
        latitude=39.4,
        longitude=-3.3,
        country="Spain",
        admin1="Castille-La Mancha",
        timezone="Europe/Madrid",
    )
    picked = pick_location_candidates("Madrid, Spain", [MADRID, prefix_noise])
    assert picked == [MADRID]


def test_lookup_weather_ambiguous():
    payload = {
        "results": [
            {
                "name": "Madrid",
                "latitude": 40.4,
                "longitude": -3.7,
                "country": "Spain",
                "admin1": "Madrid",
                "timezone": "Europe/Madrid",
                "population": 3_000_000,
            },
            {
                "name": "Madrid",
                "latitude": 4.7,
                "longitude": -74.2,
                "country": "Colombia",
                "admin1": "Cundinamarca",
                "timezone": "America/Bogota",
                "population": 135_000,
            },
        ]
    }
    text = lookup_weather(
        "Madrid",
        get_fn=lambda *a, **k: _json_response(payload),
    )
    assert "Ambiguous location" in text
    assert "Colombia" in text


def test_lookup_weather_unique_place_returns_brief():
    calls: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> SimpleNamespace:
        calls.append(url)
        if "geocoding" in url:
            return _json_response(
                {
                    "results": [
                        {
                            "name": "Madrid",
                            "latitude": 40.4165,
                            "longitude": -3.70256,
                            "country": "Spain",
                            "admin1": "Madrid",
                            "timezone": "Europe/Madrid",
                            "population": 3255944,
                        },
                        {
                            "name": "Madridejos",
                            "latitude": 39.4,
                            "longitude": -3.3,
                            "country": "Spain",
                            "admin1": "Castille-La Mancha",
                            "timezone": "Europe/Madrid",
                            "population": 10_000,
                        },
                    ]
                }
            )
        return _json_response(FORECAST_PAYLOAD)

    text = lookup_weather("Madrid, Spain", forecast_days=2, get_fn=fake_get)
    assert len(calls) == 2
    assert "Weather for Madrid, Spain" in text
    assert "### Current" in text
    assert "### Daily forecast" in text
    assert "Ambiguous" not in text


def test_lookup_weather_http_error_raises():
    def boom(*a: Any, **k: Any) -> SimpleNamespace:
        raise requests.ConnectionError("offline")

    with pytest.raises(WeatherError, match="Open-Meteo request failed"):
        search_locations("Madrid", get_fn=boom)


def test_weather_tool_missing_location():
    text = weather_tool.invoke({"location": "", "forecast_days": 1})
    assert "Location is missing" in text


def test_weather_tool_success(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.weather.lookup_weather",
        lambda location, forecast_days=1: f"OK:{location}:{forecast_days}",
    )
    text = weather_tool.invoke({"location": "Lisbon", "forecast_days": 3})
    assert text == "OK:Lisbon:3"


def test_weather_tool_provider_error(monkeypatch):
    def boom(*a: Any, **k: Any) -> str:
        raise WeatherError("timeout")

    monkeypatch.setattr("jarvis.tools.builtins.weather.lookup_weather", boom)
    text = weather_tool.invoke({"location": "Lisbon"})
    assert "Weather lookup failed" in text
    assert "Do not invent a forecast" in text
