# Weather Forecast MCP Server

> Production-ready MCP server for real-time weather forecasts using the National Weather Service API.

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server that provides Claude and other AI applications with secure, process-isolated access to weather data. Built with Python, FastMCP, and designed for production deployment.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-2025--11--25-blue.svg)](https://modelcontextprotocol.io/specification/2025-11-25)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- ✅ **3 MCP Tools**: `geocode_city`, `get_forecast`, `get_alerts`
- ✅ **Process Isolation**: Runs as independent server with scoped credentials
- ✅ **stdio Transport**: Local development with Claude Desktop
- ✅ **Docker Ready**: Production deployment with security hardening
- ✅ **No API Key Required**: Uses free National Weather Service API
- ✅ **Async/Await**: Non-blocking I/O for efficient request handling

## Quick Start

### Installation

#### Option 1: Using UV (Recommended)

Install [UV](https://docs.astral.sh/uv/) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone the repository
```bash
git clone https://github.com/slin-master/weather-forecast-mcp-server.git
cd weather-forecast-mcp-server
```
Note: Dependencies are installed automatically when running via uv.

#### Option 2: Using pip

Clone the repository
```bash
git clone https://github.com/slin-master/weather-forecast-mcp-server.git
cd weather-forecast-mcp-server
```

Install dependencies
```bash
pip install -e .
```

### Testing Locally

Start the MCP server with stdio transport:

Using UV (recommended)
```bash
uv run mcp run src/weather_forecast_mcp_server/server.py
```

Or with pip
```bash
mcp run src/weather_forecast_mcp_server/server.py
```

The server is now running and waiting for JSON-RPC connections via stdio.

### Testing with MCP Inspector

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) provides a web UI for testing:

Install inspector globally
```bash
npm install -g @modelcontextprotocol/inspector
```

Connect to your server
```bash
npx @modelcontextprotocol/inspector uv run mcp run src/weather_forecast_mcp_server/server.py
```

Open http://localhost:5173 to:
1. Connect to the server
2. Explore available tools
3. Test tool invocations with sample inputs

## Using with Claude Desktop

Add to your `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/weather-forecast-mcp-server",
        "run",
        "mcp",
        "run",
        "src/weather_forecast_mcp_server/server.py"
      ]
    }
  }
}
```

Restart Claude Desktop, then try:
- "What's the weather in Portland, Oregon?"
- "Are there any weather alerts in Miami?"
- "Will it rain in Seattle this week?"

Claude will invoke your MCP server's tools to fetch real-time data!

## Docker Deployment

For production deployments, use Docker for process isolation and security:

### Build and Run

Build the image
```bash
docker compose build
```

Run the container
```bash
docker compose up -d
```

View logs
```bash
docker compose logs -f weather-mcp
```

### Security Features

The Docker setup includes:
- ✅ Non-root user (`mcpuser`)
- ✅ Read-only filesystem
- ✅ No privilege escalation
- ✅ Resource limits (CPU/memory)
- ✅ Health checks

### HTTP Transport (Optional)

For remote access, modify `server.py` to use HTTP transport:

```python
if __name__ == "__main__":
    import sys
    if "--http" in sys.argv:
        mcp.run(transport="http", host="0.0.0.0", port=8000)
    else:
        mcp.run()  # Default stdio
```

Update the Dockerfile CMD and expose port 8000 in `compose.yml`.

## How It Works

This server implements the [MCP specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25):

```
weather-forecast-mcp-server/
├── src/weather_forecast_mcp_server/
│   └── server.py           # FastMCP server with 3 tools
├── pyproject.toml          # Dependencies and metadata
├── Dockerfile              # Production container
└── compose.yml             # Docker orchestration
```

### Architecture

1. **MCP Host** (Claude Desktop, VS Code, etc.) spawns the server process
2. **JSON-RPC 2.0** messages exchanged via stdio or HTTP
3. **FastMCP** handles protocol details (capability negotiation, tool registration)
4. **Async I/O** with httpx for non-blocking API requests
5. **Structured responses** returned as JSON to the host

### Available Tools

**`geocode_city(city_name: str)`**
- Converts city names to coordinates
- Uses Nominatim OpenStreetMap API
- Returns lat, lon, and display name

**`get_forecast(latitude: float, longitude: float)`**
- Fetches complete weather forecast
- Returns current conditions, 7-day forecast, hourly data, and alerts
- National Weather Service API (US only)

**`get_alerts(latitude: float, longitude: float)`**
- Gets active weather alerts
- Returns warnings, watches, and advisories
- Includes severity, urgency, and expiration

## Comparing to Agent Skills

This server provides the **same weather functionality** as the [Agent Skills version](https://github.com/slin-master/weather-forecast-skills), but with different architecture:

| Aspect         | Agent Skills         | MCP Server          |
|----------------|----------------------|---------------------|
| **Execution**  | In-process scripts   | Separate process    |
| **Isolation**  | Shared environment   | Process boundaries  |
| **Security**   | Client's credentials | Scoped credentials  |
| **Transport**  | Filesystem           | stdio or HTTP       |
| **Deployment** | Client-managed       | Independent service |
| **Use Case**   | Personal workflows   | Production systems  |

**When to use this MCP server:**
- Production deployments with SLAs
- Multiple clients accessing the service
- Security isolation required
- Enterprise/organizational policies
- Remote access needed (HTTP transport)

**When to use Agent Skills instead:**
- Rapid prototyping
- Personal productivity
- Trusted local code
- Filesystem-based discovery sufficient

## Supported Platforms

- ✅ [Claude Desktop](https://claude.ai/download) (stdio)
- ✅ [Claude API](https://docs.anthropic.com/en/api/mcp) (HTTP)
- ✅ [VS Code with Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot) (stdio)
- ✅ [Cursor](https://cursor.sh/) (stdio)
- ✅ Custom MCP clients (stdio or HTTP)

## API Coverage

Uses the [National Weather Service API](https://www.weather.gov/documentation/services-web-api):
- 🇺🇸 All US states and territories
- 🇵🇷 Puerto Rico, US Virgin Islands
- 🇬🇺 Guam, American Samoa

**Note**: For international weather, extend with OpenWeatherMap or WeatherAPI.

## Learn More

📖 **Read the full tutorial**: [Building Your First MCP Server](https://friedrichs-it.de/blog/weather-forecast-api-as-stdio-python-mcp-server)

This repository accompanies a comprehensive tutorial covering:
- MCP server implementation with FastMCP
- stdio vs HTTP transport
- Docker containerization for production
- Security best practices
- Comparison with Agent Skills architecture

## Requirements

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) (recommended) or pip
- Dependencies: See `pyproject.toml`
- Docker (optional, for containerized deployment)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Ideas for Contributions

- [ ] Add Resources capability (weather history data)
- [ ] Add Prompts capability (common weather queries)
- [ ] Implement caching layer (Redis)
- [ ] Add authentication for HTTP transport
- [ ] Support international weather APIs
- [ ] Add metrics and observability (Prometheus)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Attribution

Created by [Nils Friedrichs](https://friedrichs-it.de) as part of the MCP ecosystem.

Weather data from:
- [National Weather Service API](https://www.weather.gov/documentation/services-web-api)
- [Nominatim (OpenStreetMap)](https://nominatim.org/)

## Related Projects

- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Agent Skills Version](https://github.com/slin-master/weather-forecast-skills) - Filesystem-based alternative
- [LightNow MCP Registry](https://www.lightnow.ai/servers) - Discover more MCP servers

---

**Questions or feedback?** [Open an issue](https://github.com/slin-master/weather-forecast-mcp-server/issues) or [contact me](https://friedrichs-it.de/contact).
