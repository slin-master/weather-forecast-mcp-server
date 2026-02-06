FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Copy dependency files first (for layer caching)
COPY pyproject.toml ./
COPY uv.lock ./
COPY README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src ./src

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

# Expose port for HTTP transport (if using)
EXPOSE 8000

# Default to stdio transport
CMD ["uv", "run", "mcp", "run", "src/weather_forecast_mcp_server/server.py"]