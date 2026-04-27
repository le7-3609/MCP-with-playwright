# Weather MCP Client

An AI-powered weather assistant that uses the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) to connect a Gemini LLM to weather data tools for the USA and Israel.

## How It Works

The project consists of three layers:

- **`host.py`** — The main chat application. Connects to all MCP servers, collects their tools, and passes them to Gemini. Runs an interactive query loop where Gemini decides which tools to call.
- **`client.py`** — A reusable MCP client wrapper that spawns an MCP server as a subprocess and communicates with it over stdio.
- **`weather_USA.py`** — An MCP server that fetches weather alerts and forecasts from the [National Weather Service API](https://api.weather.gov).
- **`weather_Israel.py`** — An MCP server that uses Playwright to scrape weather forecasts from [weather2day.co.il](https://www.weather2day.co.il/forecast).

## Available Tools

| Tool | Server | Description |
|---|---|---|
| `get_alerts_in_USA` | weather_USA | Get active weather alerts for a US state (e.g. `CA`, `NY`) |
| `get_forecast_in_USA` | weather_USA | Get weather forecast for a lat/lon location in the USA |
| `open_weather_forecast_israel` | weather_Israel | Open a browser and navigate to the Israeli forecast site |
| `enter_weather_forecast_city_israel` | weather_Israel | Type a city name into the search field |
| `select_weather_forecast_city_israel` | weather_Israel | Click the first autocomplete suggestion |
| `get_weather_forecast_israel` | weather_Israel | Read and return the forecast text from the page |

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)
- Playwright browsers installed

### Install dependencies

```bash
uv sync
uv run playwright install chromium
```

### Configure environment

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

## Usage

```bash
uv run host.py
```

Then type your weather query at the prompt:

```
Query: What are the weather alerts in California?
Query: What is the weather forecast in Jerusalem tonight?
Query: quit
```

## Notes

- The Israel weather tool opens a visible Chromium browser window to scrape the forecast site.
- The Gemini free tier has daily request quotas. If you hit a `429 RESOURCE_EXHAUSTED` error, wait until the next day or enable billing on your Google Cloud project.
- Rate-limited requests are automatically retried up to 3 times with the delay suggested by the API.

## 📄 License

MIT License.
