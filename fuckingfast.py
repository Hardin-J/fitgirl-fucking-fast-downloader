"""
fuckingfast.py — Resolves a fuckingfast.co URL to a real download URL.

From inspecting the page JS, the download() function contains the CDN URL directly:
  window.open("https://fuckingfast.co/dl/<token>")

We extract this URL from the page source via regex — no clicking needed.
The first click might open an ad (base64 `ad` variable), second click hits the real URL.
We skip the ad by extracting the URL directly from JS.
"""

import asyncio
import re
import sys
from typing import Optional


# Matches the real CDN URL in the download() function
# e.g.: window.open("https://dl.fuckingfast.co/dl/...")
DL_URL_RE = re.compile(
    r'window\.open\(["\'](https?://(?:dl\.)?fuckingfast\.co/dl/[^"\']+)["\']',
    re.IGNORECASE,
)


async def resolve_download_url(
    page_url: str,
    timeout: int = 30_000,
    retries: int = 3,
    retry_delay: float = 3.0,
) -> Optional[str]:
    """
    Load the fuckingfast.co page and extract the real CDN download URL
    directly from the page's JavaScript source.
    Returns None on failure.
    """
    for attempt in range(1, retries + 1):
        try:
            result = await _try_resolve(page_url, timeout)
            if result:
                return result
            print(
                f"  [resolver] Attempt {attempt}/{retries}: no URL found in JS for {page_url}",
                file=sys.stderr,
            )
        except Exception as e:
            print(
                f"  [resolver] Attempt {attempt}/{retries} error: {e}",
                file=sys.stderr,
            )
        if attempt < retries:
            await asyncio.sleep(retry_delay)
    return None


async def _try_resolve(page_url: str, timeout: int) -> Optional[str]:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # Navigate and wait for JS to run
        await page.goto(page_url, wait_until="networkidle", timeout=timeout)
        await asyncio.sleep(2)

        # Extract the download() function body from the page JS
        dl_url = await page.evaluate("""() => {
            // Walk all script tags looking for the download() function
            const scripts = Array.from(document.querySelectorAll('script'));
            for (const script of scripts) {
                const src = script.innerText || script.textContent || '';
                // Match window.open("https://dl.fuckingfast.co/dl/...")
                // or the older "https://fuckingfast.co/dl/..."
                const match = src.match(/window\\.open\\(["'](https?:\\/\\/(?:dl\\.)?fuckingfast\\.co\\/dl\\/[^"']+)["']/);
                if (match) return match[1];
            }
            return null;
        }""")

        await browser.close()

    if dl_url:
        return dl_url

    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fuckingfast.py <fuckingfast_url>")
        sys.exit(1)

    async def main():
        url = sys.argv[1]
        print(f"Resolving: {url}")
        real = await resolve_download_url(url)
        if real:
            print(f"✓ Real URL: {real}")
        else:
            print("✗ Failed to resolve download URL.")
            sys.exit(1)

    asyncio.run(main())
