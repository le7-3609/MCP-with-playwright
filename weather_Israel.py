import re
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("weather-Israel")

FORECAST_URL = "https://www.weather2day.co.il/forecast"

_playwright = None
_browser = None
_page = None


@mcp.tool()
async def open_weather_forecast_israel() -> str:
    """Opens the browser and navigates to the Israeli weather forecast site."""
    global _playwright, _browser, _page
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=False)
    _page = await _browser.new_page()
    await _page.goto(FORECAST_URL)
    return "Browser opened and navigated to forecast page."


@mcp.tool()
async def enter_weather_forecast_city_israel(city: str) -> str:
    """Enters a city name into the search field on the forecast page.

    Args:
        city: The name of the city to search for.
    """
    await _page.get_by_role("textbox").fill(city)
    return f"Entered city: {city}"


@mcp.tool()
async def select_weather_forecast_city_israel() -> str:
    """Selects the first city from the dropdown suggestions list."""
    first_item = _page.locator("ul.ui-autocomplete li").first
    await first_item.wait_for()
    await first_item.click()
    return "Selected the first city from the dropdown."


@mcp.tool()
async def get_weather_forecast_israel() -> str:
    """Reads and returns the weather forecast content from the page after a city has been selected."""
    await _page.wait_for_load_state("networkidle")

    forecast = await _page.evaluate(
        """() => {
            const noise = [
                'script', 'style', 'noscript', 'iframe',
                'nav', 'header', 'footer', 'aside',
                '[role="banner"]', '[role="navigation"]',
                '[role="complementary"]', '[role="contentinfo"]',
                '.ad', '.ads', '.advertisement', '.cookie-banner',
            ];
            noise.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });

            const container =
                document.querySelector('main') ||
                document.querySelector('article') ||
                document.querySelector('[role="main"]') ||
                document.body;

            return container.innerText;
        }"""
    )

    forecast = re.sub(r"[ \t]{2,}", " ", forecast)
    forecast = re.sub(r"\n{3,}", "\n\n", forecast)
    return forecast.strip()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
