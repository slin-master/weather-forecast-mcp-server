import asyncio
import json

import httpx

from weather_forecast_mcp_server import server


class MockResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.weather.gov/mock")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(f"HTTP error {self.status_code}", request=request, response=response)


class MockAsyncClient:
    def __init__(self):
        self._calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self._calls.append((url, kwargs))
        if "/points/" in url:
            return MockResponse(
                {
                    "properties": {
                        "forecast": "https://api.weather.gov/gridpoints/SEW/124,67/forecast",
                        "forecastHourly": "https://api.weather.gov/gridpoints/SEW/124,67/forecast/hourly",
                        "relativeLocation": {
                            "properties": {
                                "city": "Seattle",
                                "state": "WA",
                            }
                        },
                    }
                }
            )
        if "forecast/hourly" in url:
            return MockResponse(
                {
                    "properties": {
                        "periods": [{"temperature": 51, "shortForecast": "Cloudy"}] * 24
                    }
                }
            )
        if "/forecast" in url:
            return MockResponse(
                {
                    "properties": {
                        "periods": [
                            {
                                "temperature": 54,
                                "temperatureUnit": "F",
                                "windSpeed": "8 mph",
                                "windDirection": "NW",
                                "shortForecast": "Partly Sunny",
                                "detailedForecast": "Partly sunny with light wind.",
                                "probabilityOfPrecipitation": {"value": 30},
                                "name": "Monday",
                            }
                        ]
                        * 14
                    }
                }
            )
        if "/alerts/active" in url:
            return MockResponse(
                {
                    "features": [
                        {
                            "properties": {
                                "event": "Flood Watch",
                                "headline": "Flood Watch in effect",
                                "severity": "Moderate",
                                "urgency": "Expected",
                            }
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected URL in test: {url}")


class MockAsyncClientForecastEmpty(MockAsyncClient):
    async def get(self, url, **kwargs):
        if "/forecast" in url and "hourly" not in url:
            return MockResponse({"properties": {"periods": []}})
        return await super().get(url, **kwargs)


class MockAsyncClientPointsError(MockAsyncClient):
    async def get(self, url, **kwargs):
        if "/points/" in url:
            return MockResponse({}, status_code=500)
        return await super().get(url, **kwargs)


def test_get_climate_normals_requires_token(monkeypatch):
    monkeypatch.setattr(server, "NOAA_TOKEN", None)
    result = asyncio.run(server.get_climate_normals("seattle-wa", "01"))
    payload = json.loads(result)
    assert payload["error"] == "NOAA_API_TOKEN not configured"


def test_get_climate_normals_rejects_invalid_month(monkeypatch):
    monkeypatch.setattr(server, "NOAA_TOKEN", "test-token")
    result = asyncio.run(server.get_climate_normals("seattle-wa", "not-a-month"))
    payload = json.loads(result)
    assert payload["error"].startswith("Invalid month:")


def test_get_forecast_maps_response_structure(monkeypatch):
    monkeypatch.setattr(server.httpx, "AsyncClient", MockAsyncClient)
    result = asyncio.run(server.get_forecast(47.6062, -122.3321))
    assert "error" not in result
    assert result["location"]["city"] == "Seattle"
    assert result["current"]["temperatureUnit"] == "F"
    assert len(result["forecast"]["periods"]) == 7
    assert len(result["hourly"]["periods"]) == 24
    assert result["alerts"][0]["event"] == "Flood Watch"


def test_get_forecast_dashboard_returns_meta_payload(monkeypatch):
    monkeypatch.setattr(server.httpx, "AsyncClient", MockAsyncClient)
    result = asyncio.run(server.get_forecast_dashboard(47.6062, -122.3321))

    assert result.isError is False
    assert result.meta is not None
    assert result.meta["location"]["city"] == "Seattle"
    assert len(result.meta["forecast"]) == 14
    assert result.meta["forecast"][0]["precipitationProbability"] == 30
    assert "Loaded dashboard forecast" in result.content[0].text


def test_get_forecast_dashboard_handles_empty_periods(monkeypatch):
    monkeypatch.setattr(server.httpx, "AsyncClient", MockAsyncClientForecastEmpty)
    result = asyncio.run(server.get_forecast_dashboard(47.6062, -122.3321))

    assert result.isError is True
    assert "No forecast periods available" in result.content[0].text


def test_get_forecast_dashboard_handles_api_error(monkeypatch):
    monkeypatch.setattr(server.httpx, "AsyncClient", MockAsyncClientPointsError)
    result = asyncio.run(server.get_forecast_dashboard(47.6062, -122.3321))

    assert result.isError is True
    assert "Error fetching dashboard forecast" in result.content[0].text


def test_dashboard_resource_is_available():
    result = asyncio.run(server.mcp.read_resource("ui://weather/dashboard"))
    assert len(result) == 1
    assert result[0].mime_type == "text/html;profile=mcp-app"
    assert "<!doctype html>" in result[0].content.lower()
