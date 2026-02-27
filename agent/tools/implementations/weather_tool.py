"""
P1-26: Weather Tool

Provides current weather and forecasts using Open-Meteo API (no API key needed).
Also supports geocoding via Open-Meteo's geocoding endpoint.

Open-Meteo docs: https://open-meteo.com/en/docs
No API key required for free tier.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
}


@dataclass
class CurrentWeather:
    """Represents current weather conditions."""

    location: str
    temperature_f: float
    temperature_c: float
    feels_like_f: float
    feels_like_c: float
    humidity: int
    wind_speed_mph: float
    wind_direction: str
    condition: str
    condition_code: int
    uv_index: float = 0.0
    precipitation_mm: float = 0.0
    visibility_km: float = 0.0
    pressure_hpa: float = 0.0

    def __str__(self) -> str:
        return (
            f"{self.location}: {self.condition}, "
            f"{self.temperature_f:.0f}°F ({self.temperature_c:.0f}°C), "
            f"Humidity {self.humidity}%, Wind {self.wind_speed_mph:.0f} mph"
        )


@dataclass
class DailyForecast:
    """Represents a single day's weather forecast."""

    date: str
    high_f: float
    low_f: float
    high_c: float
    low_c: float
    condition: str
    condition_code: int
    precipitation_mm: float
    precipitation_probability: int
    uv_index: float
    wind_speed_mph: float
    sunrise: str
    sunset: str

    def __str__(self) -> str:
        return (
            f"{self.date}: {self.condition} | "
            f"↑{self.high_f:.0f}°F / ↓{self.low_f:.0f}°F | "
            f"Precip {self.precipitation_probability}%"
        )


@dataclass
class HourlyForecast:
    """Represents an hourly weather forecast entry."""

    time: str
    temperature_f: float
    temperature_c: float
    condition: str
    condition_code: int
    precipitation_probability: int
    wind_speed_mph: float
    humidity: int

    def __str__(self) -> str:
        return (
            f"{self.time}: {self.condition}, "
            f"{self.temperature_f:.0f}°F, Precip {self.precipitation_probability}%"
        )


class WeatherTool:
    """
    Weather tool using Open-Meteo API (no API key required).

    Usage:
        weather = WeatherTool()
        current = weather.get_current("Chicago, IL")
        forecast = weather.get_forecast("Frankfort, IL", days=5)
    """

    def __init__(self) -> None:
        """Initialize the WeatherTool."""
        self._location_cache: dict[str, tuple[float, float]] = {}

    def get_current(self, location: str) -> Optional[CurrentWeather]:
        """
        Get current weather conditions for a location.

        Args:
            location: Location name (e.g., "Chicago, IL" or "60423").

        Returns:
            CurrentWeather object, or None if location not found.
        """
        coords = self._geocode(location)
        if not coords:
            logger.error("Could not geocode location: %s", location)
            return None

        lat, lon = coords

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join([
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "weather_code",
                "precipitation",
                "surface_pressure",
                "visibility",
            ]),
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "mm",
            "timezone": "America/Chicago",
        }

        try:
            url = FORECAST_URL + "?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            c = data["current"]
            code = int(c.get("weather_code", 0))
            condition = WMO_CODES.get(code, "Unknown")

            temp_f = float(c.get("temperature_2m", 0))
            temp_c = (temp_f - 32) * 5 / 9
            feels_f = float(c.get("apparent_temperature", temp_f))
            feels_c = (feels_f - 32) * 5 / 9

            return CurrentWeather(
                location=location,
                temperature_f=temp_f,
                temperature_c=temp_c,
                feels_like_f=feels_f,
                feels_like_c=feels_c,
                humidity=int(c.get("relative_humidity_2m", 0)),
                wind_speed_mph=float(c.get("wind_speed_10m", 0)),
                wind_direction=_degrees_to_compass(float(c.get("wind_direction_10m", 0))),
                condition=condition,
                condition_code=code,
                precipitation_mm=float(c.get("precipitation", 0)),
                visibility_km=float(c.get("visibility", 0)) / 1000,
                pressure_hpa=float(c.get("surface_pressure", 0)),
            )

        except Exception as e:
            logger.error("Failed to get current weather for %s: %s", location, e)
            return None

    def get_forecast(
        self,
        location: str,
        days: int = 5,
    ) -> list[DailyForecast]:
        """
        Get daily weather forecast.

        Args:
            location: Location name.
            days: Number of forecast days (1-16).

        Returns:
            List of DailyForecast objects.
        """
        coords = self._geocode(location)
        if not coords:
            return []

        lat, lon = coords
        days = min(max(days, 1), 16)

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "weather_code",
                "precipitation_sum",
                "precipitation_probability_max",
                "uv_index_max",
                "wind_speed_10m_max",
                "sunrise",
                "sunset",
            ]),
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "mm",
            "timezone": "America/Chicago",
            "forecast_days": days,
        }

        try:
            url = FORECAST_URL + "?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            daily = data["daily"]
            n = len(daily.get("time", []))
            forecasts: list[DailyForecast] = []

            for i in range(n):
                code = int(daily["weather_code"][i] or 0)
                high_f = float(daily["temperature_2m_max"][i] or 0)
                low_f = float(daily["temperature_2m_min"][i] or 0)

                forecasts.append(DailyForecast(
                    date=daily["time"][i],
                    high_f=high_f,
                    low_f=low_f,
                    high_c=(high_f - 32) * 5 / 9,
                    low_c=(low_f - 32) * 5 / 9,
                    condition=WMO_CODES.get(code, "Unknown"),
                    condition_code=code,
                    precipitation_mm=float(daily["precipitation_sum"][i] or 0),
                    precipitation_probability=int(daily["precipitation_probability_max"][i] or 0),
                    uv_index=float(daily["uv_index_max"][i] or 0),
                    wind_speed_mph=float(daily["wind_speed_10m_max"][i] or 0),
                    sunrise=daily["sunrise"][i] or "",
                    sunset=daily["sunset"][i] or "",
                ))

            return forecasts

        except Exception as e:
            logger.error("Failed to get forecast for %s: %s", location, e)
            return []

    def get_hourly(
        self,
        location: str,
        hours: int = 24,
    ) -> list[HourlyForecast]:
        """
        Get hourly weather forecast.

        Args:
            location: Location name.
            hours: Number of hours to forecast (1-168).

        Returns:
            List of HourlyForecast objects.
        """
        coords = self._geocode(location)
        if not coords:
            return []

        lat, lon = coords
        hours = min(max(hours, 1), 168)

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join([
                "temperature_2m",
                "weather_code",
                "precipitation_probability",
                "wind_speed_10m",
                "relative_humidity_2m",
            ]),
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "timezone": "America/Chicago",
            "forecast_hours": hours,
        }

        try:
            url = FORECAST_URL + "?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            hourly = data["hourly"]
            n = len(hourly.get("time", []))
            forecasts: list[HourlyForecast] = []

            for i in range(min(n, hours)):
                code = int(hourly["weather_code"][i] or 0)
                temp_f = float(hourly["temperature_2m"][i] or 0)

                forecasts.append(HourlyForecast(
                    time=hourly["time"][i],
                    temperature_f=temp_f,
                    temperature_c=(temp_f - 32) * 5 / 9,
                    condition=WMO_CODES.get(code, "Unknown"),
                    condition_code=code,
                    precipitation_probability=int(hourly["precipitation_probability"][i] or 0),
                    wind_speed_mph=float(hourly["wind_speed_10m"][i] or 0),
                    humidity=int(hourly["relative_humidity_2m"][i] or 0),
                ))

            return forecasts

        except Exception as e:
            logger.error("Failed to get hourly forecast for %s: %s", location, e)
            return []

    def get_weather_summary(self, location: str) -> str:
        """
        Get a human-readable weather summary.

        Args:
            location: Location name.

        Returns:
            Formatted weather summary string.
        """
        current = self.get_current(location)
        forecast = self.get_forecast(location, days=3)

        if not current:
            return f"Unable to get weather for {location}"

        lines = [
            f"🌤 **Weather for {location}**",
            f"Now: {current.condition}, {current.temperature_f:.0f}°F",
            f"Feels like: {current.feels_like_f:.0f}°F | Humidity: {current.humidity}%",
            f"Wind: {current.wind_speed_mph:.0f} mph {current.wind_direction}",
        ]

        if forecast:
            lines.append("\n📅 3-Day Forecast:")
            for day in forecast[:3]:
                lines.append(
                    f"  {day.date}: {day.condition} "
                    f"↑{day.high_f:.0f}°F / ↓{day.low_f:.0f}°F "
                    f"({day.precipitation_probability}% precip)"
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _geocode(self, location: str) -> Optional[tuple[float, float]]:
        """Convert location name to lat/lon coordinates."""
        if location in self._location_cache:
            return self._location_cache[location]

        params = {
            "name": location,
            "count": "1",
            "language": "en",
            "format": "json",
        }
        url = GEOCODING_URL + "?" + urllib.parse.urlencode(params)

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            results = data.get("results", [])
            if results:
                lat = float(results[0]["latitude"])
                lon = float(results[0]["longitude"])
                self._location_cache[location] = (lat, lon)
                return lat, lon

            return None

        except Exception as e:
            logger.error("Geocoding failed for '%s': %s", location, e)
            return None


def _degrees_to_compass(degrees: float) -> str:
    """Convert wind direction degrees to compass direction."""
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    idx = round(degrees / 22.5) % 16
    return directions[idx]
