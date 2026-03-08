import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from '@modelcontextprotocol/ext-apps/server';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const NWS_API_BASE = 'https://api.weather.gov';
const USER_AGENT = 'WeatherMCPAppBridge/1.0 (https://github.com/slin-master/weather-forecast-mcp-server)';
const resourceUri = 'ui://weather/dashboard';
const dashboardPath = path.resolve(__dirname, '../src/weather_forecast_mcp_server/ui/weather_dashboard.html');

const server = new McpServer({
  name: 'Weather Dashboard App Server',
  version: '1.0.0'
});

registerAppResource(
  server,
  resourceUri,
  resourceUri,
  { mimeType: RESOURCE_MIME_TYPE },
  async () => {
    const html = await fs.readFile(dashboardPath, 'utf-8');
    return {
      contents: [
        {
          uri: resourceUri,
          mimeType: RESOURCE_MIME_TYPE,
          text: html,
          _meta: {
            ui: {
              csp: {
                connectDomains: [NWS_API_BASE],
                resourceDomains: []
              }
            }
          }
        }
      ]
    };
  }
);

registerAppTool(
  server,
  'get_forecast_dashboard',
  {
    title: 'Weather Forecast Dashboard',
    description: 'Get 7-day forecast data and render interactive MCP app dashboard.',
    inputSchema: {
      latitude: z.number().describe('Latitude in decimal degrees'),
      longitude: z.number().describe('Longitude in decimal degrees')
    },
    _meta: {
      ui: {
        resourceUri
      }
    }
  },
  async ({ latitude, longitude }) => {
    try {
      const pointsRes = await fetch(`${NWS_API_BASE}/points/${latitude},${longitude}`, {
        headers: { 'User-Agent': USER_AGENT }
      });

      if (pointsRes.status === 404) {
        return {
          content: [
            { type: 'text', text: 'Location is outside National Weather Service coverage.' }
          ],
          isError: true
        };
      }

      if (!pointsRes.ok) {
        throw new Error(`NWS points request failed (${pointsRes.status})`);
      }

      const pointsData = await pointsRes.json();
      const forecastUrl = pointsData?.properties?.forecast;
      if (!forecastUrl) {
        throw new Error('Missing forecast URL in NWS points response.');
      }

      const forecastRes = await fetch(forecastUrl, {
        headers: { 'User-Agent': USER_AGENT }
      });
      if (!forecastRes.ok) {
        throw new Error(`NWS forecast request failed (${forecastRes.status})`);
      }

      const forecastData = await forecastRes.json();
      const periods = (forecastData?.properties?.periods || []).slice(0, 14);
      if (!periods.length) {
        return {
          content: [{ type: 'text', text: 'No forecast periods available for this location.' }],
          isError: true
        };
      }

      const city = pointsData?.properties?.relativeLocation?.properties?.city || 'Unknown';
      const state = pointsData?.properties?.relativeLocation?.properties?.state || '';

      const chartData = periods.map((period) => ({
        name: period?.name,
        temperature: period?.temperature,
        temperatureUnit: period?.temperatureUnit || 'F',
        windSpeed: period?.windSpeed || '0 mph',
        shortForecast: period?.shortForecast || '',
        precipitationProbability: period?.probabilityOfPrecipitation?.value || 0
      }));

      return {
        content: [
          {
            type: 'text',
            text: `Loaded dashboard forecast for ${city}${state ? `, ${state}` : ''}: ${chartData[0]?.shortForecast || 'Forecast loaded'}.`
          }
        ],
        _meta: {
          viewUUID: randomUUID(),
          forecast: chartData,
          location: {
            lat: latitude,
            lon: longitude,
            city,
            state
          }
        }
      };
    } catch (error) {
      return {
        content: [
          { type: 'text', text: `Error fetching dashboard forecast: ${error instanceof Error ? error.message : String(error)}` }
        ],
        isError: true
      };
    }
  }
);

await server.connect(new StdioServerTransport());
