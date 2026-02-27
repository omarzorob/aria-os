"""
P1-23: Maps Tool

Provides navigation and location services via Google Maps intents on Android.
Supports directions, ETA, nearby search, and navigation launch.

Uses Google Maps URI scheme via ADB intents.
All geo operations use the Google Maps app (com.google.android.apps.maps).

Environment variables:
- GOOGLE_MAPS_API_KEY: Optional, for server-side distance/route calculations.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

MAPS_PACKAGE = "com.google.android.apps.maps"
MAPS_API_BASE = "https://maps.googleapis.com/maps/api"


@dataclass
class DirectionsResult:
    """Represents navigation directions."""

    origin: str
    destination: str
    mode: str
    distance: str
    duration: str
    steps: list[str]
    polyline: str = ""

    def __str__(self) -> str:
        return (
            f"{self.origin} → {self.destination} "
            f"({self.mode}) — {self.distance}, ~{self.duration}"
        )


@dataclass
class NearbyPlace:
    """Represents a nearby place from Google Maps."""

    name: str
    address: str
    place_id: str = ""
    rating: float = 0.0
    distance: str = ""
    category: str = ""
    phone: str = ""
    is_open: Optional[bool] = None

    def __str__(self) -> str:
        rating_str = f" ★{self.rating:.1f}" if self.rating else ""
        return f"{self.name}{rating_str} — {self.address}"


class MapsTool:
    """
    Navigation and maps tool using Google Maps intents.

    Usage:
        maps = MapsTool(adb_bridge)
        maps.open_navigation("123 Main St, Chicago, IL")
        directions = maps.get_directions("Home", "Work", mode="driving")
    """

    TRAVEL_MODES = {
        "driving": "d",
        "walking": "w",
        "bicycling": "b",
        "transit": "r",
    }

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the MapsTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb
        self.api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    def get_directions(
        self,
        origin: str,
        destination: str,
        mode: str = "driving",
    ) -> Optional[DirectionsResult]:
        """
        Get turn-by-turn directions between two locations.

        If GOOGLE_MAPS_API_KEY is set, uses the Directions API for detailed steps.
        Otherwise opens Google Maps on the device.

        Args:
            origin: Starting location (address or "current location").
            destination: Destination address.
            mode: Travel mode ("driving", "walking", "bicycling", "transit").

        Returns:
            DirectionsResult if API key is set, or None (opens app instead).
        """
        if self.api_key:
            return self._get_directions_api(origin, destination, mode)
        else:
            self.open_navigation(destination, mode=mode)
            return None

    def get_eta(
        self,
        destination: str,
        origin: str = "current+location",
        mode: str = "driving",
    ) -> Optional[str]:
        """
        Get estimated time of arrival to destination.

        Args:
            destination: Destination address.
            origin: Starting point (default: current location).
            mode: Travel mode.

        Returns:
            ETA string like "23 mins" or None if unavailable.
        """
        if self.api_key:
            try:
                result = self._get_directions_api(origin, destination, mode)
                if result:
                    return result.duration
            except Exception as e:
                logger.warning("ETA API call failed: %s", e)

        # Fallback: open Maps and try to read from screen
        self.get_directions(origin, destination, mode)
        return None

    def search_nearby(
        self,
        query: str,
        location: str = "current+location",
        radius: int = 5000,
    ) -> list[NearbyPlace]:
        """
        Search for nearby places.

        Args:
            query: Type of place (e.g., "restaurant", "gas station", "pharmacy").
            location: Center of search (address or "current+location").
            radius: Search radius in meters.

        Returns:
            List of NearbyPlace objects.
        """
        if self.api_key:
            return self._nearby_search_api(query, location, radius)
        else:
            # Fallback: open Maps search
            self._open_maps_search(query, location)
            return []

    def open_navigation(
        self,
        destination: str,
        mode: str = "driving",
        origin: Optional[str] = None,
    ) -> bool:
        """
        Open Google Maps navigation to destination.

        Args:
            destination: Destination address.
            mode: Travel mode.
            origin: Optional origin (default: current location).

        Returns:
            True if Maps was opened successfully.
        """
        try:
            mode_char = self.TRAVEL_MODES.get(mode.lower(), "d")
            enc_dest = urllib.parse.quote(destination)

            if origin:
                enc_origin = urllib.parse.quote(origin)
                maps_uri = (
                    f"google.navigation:q={enc_dest}"
                    f"&origin={enc_origin}"
                    f"&mode={mode_char}"
                )
            else:
                maps_uri = f"google.navigation:q={enc_dest}&mode={mode_char}"

            self.adb._shell(
                f"am start -a android.intent.action.VIEW "
                f"-d '{maps_uri}' "
                f"-p {MAPS_PACKAGE}"
            )
            logger.info("Opened navigation to: %s (%s)", destination, mode)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to open navigation: %s", e)
            return False

    def open_location(self, location: str, label: Optional[str] = None) -> bool:
        """
        Open Google Maps at a specific location.

        Args:
            location: Address or lat,lng coordinates.
            label: Optional map pin label.

        Returns:
            True if Maps was opened.
        """
        try:
            enc_loc = urllib.parse.quote(location)
            label_part = f"({urllib.parse.quote(label)})" if label else ""
            maps_uri = f"geo:0,0?q={enc_loc}{label_part}"

            self.adb._shell(
                f"am start -a android.intent.action.VIEW "
                f"-d '{maps_uri}' "
                f"-p {MAPS_PACKAGE}"
            )
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to open location %s: %s", location, e)
            return False

    # ------------------------------------------------------------------
    # Google Maps API (requires API key)
    # ------------------------------------------------------------------

    def _get_directions_api(
        self,
        origin: str,
        destination: str,
        mode: str,
    ) -> Optional[DirectionsResult]:
        """Use Google Maps Directions API."""
        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "key": self.api_key,
        }
        url = f"{MAPS_API_BASE}/directions/json?" + urllib.parse.urlencode(params)

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            if data.get("status") != "OK" or not data.get("routes"):
                logger.warning("Directions API returned: %s", data.get("status"))
                return None

            route = data["routes"][0]["legs"][0]
            steps = [
                re.sub(r"<[^>]+>", "", step["html_instructions"])
                for step in route["steps"]
            ]

            return DirectionsResult(
                origin=origin,
                destination=destination,
                mode=mode,
                distance=route["distance"]["text"],
                duration=route["duration"]["text"],
                steps=steps,
                polyline=data["routes"][0].get("overview_polyline", {}).get("points", ""),
            )

        except Exception as e:
            logger.error("Directions API error: %s", e)
            return None

    def _nearby_search_api(
        self,
        query: str,
        location: str,
        radius: int,
    ) -> list[NearbyPlace]:
        """Use Google Maps Places API for nearby search."""
        params = {
            "query": query,
            "key": self.api_key,
        }
        if location != "current+location":
            params["location"] = location
        params["radius"] = str(radius)

        url = (
            f"{MAPS_API_BASE}/place/textsearch/json?"
            + urllib.parse.urlencode(params)
        )

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())

            places: list[NearbyPlace] = []
            for p in data.get("results", [])[:10]:
                places.append(NearbyPlace(
                    name=p.get("name", ""),
                    address=p.get("formatted_address", ""),
                    place_id=p.get("place_id", ""),
                    rating=float(p.get("rating", 0)),
                    category=", ".join(p.get("types", [])[:2]),
                    is_open=p.get("opening_hours", {}).get("open_now"),
                ))
            return places

        except Exception as e:
            logger.error("Nearby search API error: %s", e)
            return []

    def _open_maps_search(self, query: str, location: str) -> None:
        """Open Maps app with a search query."""
        try:
            enc_query = urllib.parse.quote(f"{query} near {location}")
            self.adb._shell(
                f"am start -a android.intent.action.VIEW "
                f"-d 'geo:0,0?q={enc_query}' "
                f"-p {MAPS_PACKAGE}"
            )
        except ADBBridge.ADBError as e:
            logger.error("Failed to open Maps search: %s", e)


import re  # noqa: E402 (needed for html tag stripping in directions steps)
