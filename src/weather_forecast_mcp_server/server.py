#!/usr/bin/env python3
"""
Weather forecast MCP server with Tools and Resources using National Weather Service API.
"""
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("weather-server")

# Constants
NWS_API_BASE = "https://api.weather.gov"
NOAA_CDO_BASE = "https://www.ncei.noaa.gov/cdo-web/api/v2"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "WeatherMCPServer/2.0 (https://github.com/slin-master/weather-forecast-mcp-server)"
NOAA_TOKEN = os.getenv("NOAA_API_TOKEN")
UI_DASHBOARD_PATH = Path(__file__).parent / "ui" / "weather_dashboard.html"
MCP_APP_MIME_TYPE = "text/html;profile=mcp-app"


def _enable_mcp_apps_capability() -> None:
    """
    FastMCP does not expose experimental capabilities in its high-level API.
    Patch initialization options so hosts can detect MCP App support.
    """
    base_create_init = mcp._mcp_server.create_initialization_options

    def patched_create_initialization_options(notification_options=None, experimental_capabilities=None):
        merged = dict(experimental_capabilities or {})
        merged.setdefault("mcpui", {"mimeTypes": [MCP_APP_MIME_TYPE]})
        return base_create_init(
            notification_options=notification_options,
            experimental_capabilities=merged,
        )

    mcp._mcp_server.create_initialization_options = patched_create_initialization_options


_enable_mcp_apps_capability()

# Month name to number mapping
MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}


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


@mcp.resource(
    "ui://weather/dashboard",
    mime_type=MCP_APP_MIME_TYPE,
    meta={
        "ui": {
            "csp": {
                "connectDomains": [
                    "https://api.weather.gov",
                ],
                "resourceDomains": [],
            }
        }
    },
)
async def weather_dashboard_resource() -> str:
    """
    Serve the weather dashboard app UI for MCP hosts that support app rendering.
    """
    if UI_DASHBOARD_PATH.exists():
        return UI_DASHBOARD_PATH.read_text(encoding="utf-8")

    return """<!DOCTYPE html><html><body><h1>Weather Dashboard</h1><p>Dashboard UI file is missing.</p></body></html>"""


@mcp.tool(
    title="Weather Forecast Dashboard",
    description="Get a 7-day weather forecast payload for the dashboard app.",
    meta={
        "ui": {
            "resourceUri": "ui://weather/dashboard"
        },
        # Backward-compatible key for hosts still expecting flat metadata.
        "ui/resourceUri": "ui://weather/dashboard"
    }
)
async def get_forecast_dashboard(latitude: float, longitude: float) -> CallToolResult:
    """
    Get weather forecast data formatted for MCP App dashboard rendering.
    """
    async with httpx.AsyncClient() as client:
        try:
            points_response = await client.get(
                f"{NWS_API_BASE}/points/{latitude},{longitude}",
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )

            if points_response.status_code == 404:
                return CallToolResult(
                    content=[TextContent(type="text", text="Location is outside National Weather Service coverage.")],
                    isError=True
                )

            points_response.raise_for_status()
            points_data = points_response.json()

            forecast_url = points_data["properties"]["forecast"]
            forecast_response = await client.get(
                forecast_url,
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()

            periods = forecast_data["properties"]["periods"][:14]
            if not periods:
                return CallToolResult(
                    content=[TextContent(type="text", text="No forecast periods available for this location.")],
                    isError=True
                )

            chart_data = [
                {
                    "name": period.get("name"),
                    "temperature": period.get("temperature"),
                    "temperatureUnit": period.get("temperatureUnit", "F"),
                    "windSpeed": period.get("windSpeed", "0 mph"),
                    "shortForecast": period.get("shortForecast", ""),
                    "precipitationProbability": (period.get("probabilityOfPrecipitation") or {}).get("value", 0) or 0,
                }
                for period in periods
            ]

            city = points_data["properties"]["relativeLocation"]["properties"].get("city", "Unknown")
            state = points_data["properties"]["relativeLocation"]["properties"].get("state", "")
            summary = chart_data[0]["shortForecast"] or "Forecast loaded"
            location_label = f"{city}, {state}".strip(", ")

            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Loaded dashboard forecast for {location_label}: {summary}."
                    )
                ],
                _meta={
                    "viewUUID": str(uuid4()),
                    "forecast": chart_data,
                    "location": {
                        "lat": latitude,
                        "lon": longitude,
                        "city": city,
                        "state": state,
                    }
                }
            )

        except (httpx.HTTPError, KeyError, IndexError) as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error fetching dashboard forecast: {str(e)}")],
                isError=True
            )


@mcp.resource("weather://climate/normals/{location}/{month}")
async def get_climate_normals(location: str, month: str) -> str:
    """
    Get 30-year climate normals (1991-2020) for a location and month.

    Provides average temperature, precipitation, and other climate statistics
    to compare current conditions against historical baselines.

    URI format: weather://climate/normals/{location}/{month}
    - location: City name (e.g., "seattle-wa", "new-york-ny")
    - month: Month number 01-12 or name (e.g., "01", "january")

    Example URIs:
    - weather://climate/normals/seattle-wa/01
    - weather://climate/normals/portland-or/july
    - weather://climate/normals/miami-fl/12
    """
    if not NOAA_TOKEN:
        return json.dumps({
            "error": "NOAA_API_TOKEN not configured",
            "help": "Get a free token at https://www.ncdc.noaa.gov/cdo-web/token",
            "instructions": "Set environment variable: export NOAA_API_TOKEN='your_token'"
        }, indent=2)

    # Parameters are provided by the MCP runtime based on the URI template
    location_slug = (location or "").strip()
    month_input = (month or "").strip().lower()

    if not location_slug or not month_input:
        return json.dumps({
            "error": "Invalid parameters",
            "expected": "weather://climate/normals/{location}/{month}",
            "received": {
                "location": location,
                "month": month,
            }
        }, indent=2)

    # Normalize month to number
    if month_input in MONTH_MAP:
        month = MONTH_MAP[month_input]
    elif month_input.isdigit() and 1 <= int(month_input) <= 12:
        month = month_input.zfill(2)
    else:
        return json.dumps({
            "error": f"Invalid month: {month_input}",
            "valid_formats": "01-12 or january-december"
        }, indent=2)

    # Parse location (e.g., "seattle-wa" -> "Seattle, WA")
    location_parts = location_slug.split('-')
    if len(location_parts) < 2:
        return json.dumps({
            "error": "Invalid location format",
            "expected": "city-state (e.g., seattle-wa)",
            "received": location_slug
        }, indent=2)

    city = ' '.join(location_parts[:-1]).title()
    state = location_parts[-1].upper()
    location_name = f"{city}, {state}"

    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Geocode to find nearest NOAA station
            geocode_response = await client.get(
                f"{NOMINATIM_BASE}/search",
                params={
                    "q": location_name,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "us"
                },
                headers={"User-Agent": USER_AGENT},
                timeout=10.0
            )
            geocode_response.raise_for_status()
            geocode_results = geocode_response.json()

            if not geocode_results:
                return json.dumps({
                    "error": f"Location not found: {location_name}"
                }, indent=2)

            lat = float(geocode_results[0]["lat"])
            lon = float(geocode_results[0]["lon"])

            # Step 2: Find nearest NOAA station with NORMAL_MLY data
            # Search within ~50km radius
            extent = f"{lat - 0.5},{lon - 0.5},{lat + 0.5},{lon + 0.5}"

            stations_response = await client.get(
                f"{NOAA_CDO_BASE}/stations",
                headers={
                    "token": NOAA_TOKEN,
                    "User-Agent": USER_AGENT
                },
                params={
                    "datasetid": "NORMAL_MLY",
                    "extent": extent,
                    "limit": 5,
                    "sortfield": "datacoverage",
                    "sortorder": "desc"
                },
                timeout=15.0
            )
            stations_response.raise_for_status()
            stations_data = stations_response.json()

            if not stations_data.get("results"):
                return json.dumps({
                    "error": "No climate stations found near location",
                    "location": location_name,
                    "coordinates": {"lat": lat, "lon": lon},
                    "note": "Climate normals may not be available for all locations"
                }, indent=2)

            station = stations_data["results"][0]
            station_id = station["id"]

            # Step 3: Fetch monthly climate normals
            # Dataset: NORMAL_MLY (Monthly Normals)
            # Data types: MLY-TAVG-NORMAL, MLY-TMAX-NORMAL, MLY-TMIN-NORMAL, MLY-PRCP-NORMAL

            start_date = f"2010-{month}-01"  # Normals dataset uses 2010 as base year
            end_date = f"2010-{month}-01"

            data_response = await client.get(
                f"{NOAA_CDO_BASE}/data",
                headers={
                    "token": NOAA_TOKEN,
                    "User-Agent": USER_AGENT
                },
                params={
                    "datasetid": "NORMAL_MLY",
                    "stationid": station_id,
                    "startdate": start_date,
                    "enddate": end_date,
                    "datatypeid": [
                        "MLY-TAVG-NORMAL",  # Average temperature
                        "MLY-TMAX-NORMAL",  # Average maximum
                        "MLY-TMIN-NORMAL",  # Average minimum
                        "MLY-PRCP-NORMAL",  # Precipitation
                    ],
                    "limit": 100,
                    "units": "standard"  # Fahrenheit, inches
                },
                timeout=15.0
            )
            data_response.raise_for_status()
            climate_data = data_response.json()

            if not climate_data.get("results"):
                return json.dumps({
                    "error": "No climate normal data available",
                    "station": station["name"],
                    "month": month
                }, indent=2)

            # Parse data types into structured format
            normals = {}
            for record in climate_data["results"]:
                datatype = record["datatype"]
                value = record["value"]

                if datatype == "MLY-TAVG-NORMAL":
                    normals["avg_temp_f"] = value / 10.0  # Tenths of degrees
                elif datatype == "MLY-TMAX-NORMAL":
                    normals["avg_high_f"] = value / 10.0
                elif datatype == "MLY-TMIN-NORMAL":
                    normals["avg_low_f"] = value / 10.0
                elif datatype == "MLY-PRCP-NORMAL":
                    normals["avg_precipitation_inches"] = value / 100.0  # Hundredths of inches

            return json.dumps({
                "location": {
                    "name": location_name,
                    "coordinates": {"lat": lat, "lon": lon},
                    "station": station["name"],
                    "station_id": station_id,
                    "elevation_meters": station.get("elevation"),
                },
                "period": "1991-2020",  # Current normals period
                "month": {
                    "number": month,
                    "name": list(MONTH_MAP.keys())[list(MONTH_MAP.values()).index(month)]
                },
                "normals": normals,
                "metadata": {
                    "source": "NOAA Climate Data Online",
                    "dataset": "NORMAL_MLY",
                    "units": {
                        "temperature": "Fahrenheit",
                        "precipitation": "inches"
                    }
                }
            }, indent=2)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return json.dumps({
                    "error": "Rate limit exceeded",
                    "limit": "5 requests/second, 10,000/day",
                    "retry_after": e.response.headers.get("Retry-After", "60 seconds")
                }, indent=2)
            return json.dumps({
                "error": f"NOAA API error: {e.response.status_code}",
                "message": str(e)
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": f"Failed to fetch climate data: {str(e)}"
            }, indent=2)
