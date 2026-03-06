import asyncio
import json

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
            raise RuntimeError(f"HTTP error {self.status_code}")


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
                            }
                        ]
                        * 7
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
