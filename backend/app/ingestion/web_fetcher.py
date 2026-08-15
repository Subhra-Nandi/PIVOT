"""Fetching raw HTML for a product page — static-first, Firecrawl fallback.

Most product pages (verified: SparkFun, Adafruit) serve full content without
JS execution, so a plain HTTP GET is tried first: free, fast, no external API
call. Firecrawl is a paid/rate-limited fallback for JS-heavy or bot-walled
sites (verified: Bolt Depot 403s a plain GET) — reached for only when the
static fetch fails outright or comes back too thin to be useful.

`FIRECRAWL_API_KEY` is read lazily (inside `_fetch_via_firecrawl`, not at
import time) so a missing key only breaks the fallback path, not every static
fetch that never needed it.
"""

from __future__ import annotations

import os

import httpx

# A generic desktop browser UA — many sites 403 the default httpx/requests UA
# even when they'd happily serve a real browser (verified: works for SparkFun,
# Adafruit; Bolt Depot still 403s regardless, which is the Firecrawl case).
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Below this many bytes of response body, treat the static fetch as "thin"
# (likely a JS shell or an anti-bot interstitial) and fall through to
# Firecrawl rather than parsing near-empty content.
_THIN_RESPONSE_THRESHOLD = 2000

_STATIC_TIMEOUT_SECONDS = 15.0


class FetchError(RuntimeError):
    """Raised when a URL can't be fetched by either the static path or
    Firecrawl (e.g. Firecrawl unconfigured and static fetch also failed)."""


def _fetch_static(url: str) -> str | None:
    """Try a plain HTTP GET. Returns the HTML body, or None if the fetch
    failed or came back too thin to be worth parsing."""
    try:
        response = httpx.get(
            url,
            headers=_BROWSER_HEADERS,
            timeout=_STATIC_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None

    if response.status_code >= 400:
        return None
    if len(response.text) < _THIN_RESPONSE_THRESHOLD:
        return None
    return response.text


def _fetch_via_firecrawl(url: str) -> str:
    """Fetch via the Firecrawl API (handles JS rendering + anti-bot).

    Raises FetchError if FIRECRAWL_API_KEY isn't set, or if the Firecrawl
    call itself fails.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise FetchError(
            f"Static fetch of '{url}' failed or was too thin, and "
            "FIRECRAWL_API_KEY is not set — cannot fall back to Firecrawl."
        )

    from firecrawl import FirecrawlApp  # imported lazily: optional dep for callers that never hit this path

    app = FirecrawlApp(api_key=api_key)
    try:
        data = app.scrape_url(url, params={"formats": ["html"]})
    except Exception as exc:  # Firecrawl SDK raises plain Exception on API errors
        raise FetchError(f"Firecrawl fetch of '{url}' failed: {exc}") from exc

    html = data.get("html") if isinstance(data, dict) else None
    if not html:
        raise FetchError(f"Firecrawl returned no HTML content for '{url}'.")
    return html


def fetch_html(url: str) -> tuple[str, str]:
    """Fetch a URL's HTML, static-first with a Firecrawl fallback.

    Returns (html, fetch_method) where fetch_method is "static" or
    "firecrawl" — callers use this to note provenance / explain a slower
    response. Raises FetchError if neither path produces usable HTML.
    """
    html = _fetch_static(url)
    if html is not None:
        return html, "static"
    return _fetch_via_firecrawl(url), "firecrawl"
