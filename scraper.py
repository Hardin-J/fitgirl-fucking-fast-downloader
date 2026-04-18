"""
scraper.py — Extracts all fuckingfast.co download links from a paste page.

paste.fitgirl-repacks.site uses PrivateBin — the content is encrypted and
decrypted client-side via JavaScript (using the URL #hash as the key).
We use Playwright to load the page, wait for decryption, then extract links.
"""

import asyncio
import sys
from dataclasses import dataclass
from typing import List
from urllib.parse import unquote

from playwright.async_api import async_playwright


@dataclass
class DownloadLink:
    filename: str
    url: str


async def scrape_links_async(paste_url: str, retries: int = 3) -> List[DownloadLink]:
    """
    Use Playwright to load the PrivateBin paste page (which decrypts via JS)
    and extract all fuckingfast.co download links.
    """
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            result = await _scrape_attempt(paste_url)
            if result:
                return result
            print(f"  [scraper] Attempt {attempt}/{retries}: no links found, retrying…", file=sys.stderr)
        except Exception as e:
            last_error = e
            print(f"  [scraper] Attempt {attempt}/{retries} failed: {e}", file=sys.stderr)
        if attempt < retries:
            await asyncio.sleep(3)
    raise RuntimeError(f"Scraping failed after {retries} attempts: {last_error}")


async def _scrape_attempt(paste_url: str) -> List[DownloadLink]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate — use load event (not domcontentloaded) with a generous timeout
        await page.goto(paste_url, wait_until="load", timeout=60_000)

        # Wait for PrivateBin JS to decrypt and render the content.
        # We wait until at least one fuckingfast.co link appears in the DOM.
        try:
            await page.wait_for_selector(
                "a[href*='fuckingfast']",
                timeout=20_000,
                state="attached",
            )
        except Exception:
            # Fallback: wait longer
            await asyncio.sleep(10)

        # Extract all <a href="...fuckingfast..."> links via JS
        raw_links = await page.evaluate("""() => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors
                .filter(a => a.href.includes('fuckingfast'))
                .map(a => ({ href: a.href, text: a.innerText.trim() }));
        }""")

        await browser.close()

    links: List[DownloadLink] = []
    seen = set()
    for item in raw_links:
        href = item["href"].strip()
        if href in seen:
            continue
        seen.add(href)
        filename = _extract_filename(href, item.get("text", ""))
        links.append(DownloadLink(filename=filename, url=href))

    return links


def scrape_links(paste_url: str) -> List[DownloadLink]:
    """Synchronous wrapper around scrape_links_async."""
    return asyncio.run(scrape_links_async(paste_url))


def _extract_filename(url: str, anchor_text: str) -> str:
    """
    Derive a filename from the URL fragment.
    fuckingfast.co URLs look like:
      https://fuckingfast.co/ek2zu2cfsi1b#WWE_2K23_--_fitgirl-repacks.site_--_.part001.rar
    The fragment after '#' is the filename (with underscores for spaces/dashes).
    """
    if "#" in url:
        fragment = url.split("#", 1)[1]
        filename = unquote(fragment).replace("_", " ").strip()
        if filename:
            return filename

    # Fallback: anchor text
    if anchor_text and "." in anchor_text:
        return anchor_text.strip()

    # Last resort: URL path segment
    return url.rstrip("/").split("/")[-1] or "unknown_file"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <paste_url>")
        sys.exit(1)
    results = scrape_links(sys.argv[1])
    for i, dl in enumerate(results, 1):
        print(f"{i:>4}. [{dl.filename}]  →  {dl.url}")
    print(f"\nTotal: {len(results)} link(s) found.")
