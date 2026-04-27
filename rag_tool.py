import re
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("rag")


def _clean_text(raw: str) -> str:
    """Collapse excessive blank lines and whitespace."""
    text = re.sub(r"[ \t]{2,}", " ", raw)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@mcp.tool()
async def fetch_page_content(url: str) -> str:
    """Fetches a web page, strips away noise (scripts, ads, navigation…) and
    returns the clean readable text so the LLM can answer questions directly
    from the page content (RAG).

    Args:
        url: Full URL of the page to fetch (e.g. https://en.wikipedia.org/wiki/Python).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            # Block ads / trackers to keep the page lean
            await page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ("image", "media", "font", "stylesheet")
                else route.continue_(),
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            content = await page.evaluate(
                """() => {
                    // Remove non-content elements
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

                    const title = document.title || '';

                    // Prefer a semantic content container when available
                    const container =
                        document.querySelector('main') ||
                        document.querySelector('article') ||
                        document.querySelector('[role="main"]') ||
                        document.body;

                    return `Page: ${title}\\nURL: ${location.href}\\n\\n${container.innerText}`;
                }"""
            )
        finally:
            await browser.close()

    return _clean_text(content)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
