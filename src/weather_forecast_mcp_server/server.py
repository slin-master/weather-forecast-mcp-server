#!/usr/bin/env python3
"""
Weather forecast MCP server using National Weather Service API.
"""
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("weather-forecast-mcp-server")

# Constants
NWS_API_BASE = "https://api.weather.gov"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "WeatherMCPServer/1.0"


@mcp.tool()
async def geocode_city(city_name: str) -> dict[str, Any]:
    """
    Convert a city name to geographic coordinates.

    Args:
        city_name: City name (e.g., "San Francisco, CA" or "Portland, Oregon")

    Returns:
        Dictionary with lat, lon, and display_name, or error message
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{NOMINATIM_BASE}/search",
                params={
                    "q": city_name,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "us"  # NWS is US-only
                },
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            response.raise_for_status()

            results = response.json()
            if not results:
                return {"error": f"City not found: {city_name}"}

            location = results[0]
            return {
                "lat": float(location["lat"]),
                "lon": float(location["lon"]),
                "display_name": location["display_name"]
            }
        except httpx.HTTPError as e:
            return {"error": f"Geocoding failed: {str(e)}"}


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> dict[str, Any]:
    """
    Get weather forecast for specific coordinates.

    Fetches current conditions, 7-day forecast, hourly predictions,
    and active weather alerts from the National Weather Service.

    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees

    Returns:
        Dictionary containing location info, current conditions,
        forecast periods, hourly data, and active alerts
    """
    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Get grid point metadata
            points_response = await client.get(
                f"{NWS_API_BASE}/points/{latitude},{longitude}",
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )

            if points_response.status_code == 404:
                return {
                    "error": "Location not covered by National Weather Service. "
                             "This API only supports US territories."
                }

            points_response.raise_for_status()
            points_data = points_response.json()

            # Step 2: Fetch forecast and hourly data
            forecast_url = points_data["properties"]["forecast"]
            hourly_url = points_data["properties"]["forecastHourly"]

            forecast_response = await client.get(
                forecast_url,
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()

            hourly_response = await client.get(
                hourly_url,
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            hourly_response.raise_for_status()
            hourly_data = hourly_response.json()

            # Step 3: Check for active alerts
            alerts_response = await client.get(
                f"{NWS_API_BASE}/alerts/active",
                params={"point": f"{latitude},{longitude}"},
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            alerts_response.raise_for_status()
            alerts_data = alerts_response.json()

            # Extract current period
            current_period = forecast_data["properties"]["periods"][0]

            return {
                "location": {
                    "lat": latitude,
                    "lon": longitude,
                    "city": points_data["properties"]["relativeLocation"]["properties"]["city"],
                    "state": points_data["properties"]["relativeLocation"]["properties"]["state"]
                },
                "current": {
                    "temperature": current_period["temperature"],
                    "temperatureUnit": current_period["temperatureUnit"],
                    "windSpeed": current_period["windSpeed"],
                    "windDirection": current_period["windDirection"],
                    "shortForecast": current_period["shortForecast"],
                    "detailedForecast": current_period["detailedForecast"]
                },
                "forecast": {
                    "periods": forecast_data["properties"]["periods"][:7]
                },
                "hourly": {
                    "periods": hourly_data["properties"]["periods"][:24]
                },
                "alerts": [
                    {
                        "event": alert["properties"]["event"],
                        "headline": alert["properties"]["headline"],
                        "severity": alert["properties"]["severity"],
                        "urgency": alert["properties"]["urgency"]
                    }
                    for alert in alerts_data.get("features", [])
                ]
            }

        except httpx.HTTPError as e:
            return {"error": f"API error: {str(e)}"}
        except (KeyError, IndexError) as e:
            return {"error": f"Unexpected API response format: {str(e)}"}


@mcp.tool()
async def get_alerts(latitude: float, longitude: float) -> dict[str, Any]:
    """
    Get active weather alerts for a location.

    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees

    Returns:
        Dictionary with list of active alerts or error message
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{NWS_API_BASE}/alerts/active",
                params={"point": f"{latitude},{longitude}"},
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            response.raise_for_status()
            alerts_data = response.json()

            alerts = [
                {
                    "event": alert["properties"]["event"],
                    "headline": alert["properties"]["headline"],
                    "description": alert["properties"]["description"],
                    "severity": alert["properties"]["severity"],
                    "urgency": alert["properties"]["urgency"],
                    "onset": alert["properties"]["onset"],
                    "expires": alert["properties"]["expires"]
                }
                for alert in alerts_data.get("features", [])
            ]

            return {
                "count": len(alerts),
                "alerts": alerts
            }

        except httpx.HTTPError as e:
            return {"error": f"Failed to fetch alerts: {str(e)}"}
