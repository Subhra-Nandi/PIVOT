"""Catalog-URL crawl — discover product links from a listing page, then
enrich the first N via `ingest_url()`. The "wow" bonus path from the Phase 2
plan: paste a listing URL, get back real per-product records with a "load
more" cursor, without the user hand-picking each product URL.

Two-stage, credit-conscious by design:
1. `discover_product_links()` — ONE Firecrawl crawl job (not one call per
   page) walks the listing and its sibling/child category pages, returning
   every same-domain link that looks like a product detail page.
2. `ingest_catalog_url()` enriches only `limit` links per call via
   `ingest_url()` (itself cached), and caches the FULL discovered link list
   on disk keyed by `catalog_url` so "load more" pages through the cached
   list rather than re-crawling — a repeat crawl re-spends ~1 Firecrawl
   credit per page, which "load more" must not trigger.

Why `includePaths` is derived, not hardcoded: verified live against Bolt
Depot's `/Hex_bolts` listing, Firecrawl's crawl defaults to only children of
the seed path — it never reaches sibling category pages like
`/Hex_bolts_Stainless_steel_18-8`, so 0 product links were found. Passing
`includePaths=['^/Hex_bolts.*', ...]` (the seed URL's own path as a prefix)
fixed this, because Bolt Depot's category-variant URLs are literally the
listing slug plus a suffix. That prefix-of-the-seed-path heuristic is
generic enough to try on another site's listing without being told its
category-URL convention in advance; it isn't guaranteed to work everywhere.

`product_url_pattern` has no universal default — "what does a product detail
URL look like" is a per-site convention, not something a crawler can infer
from arbitrary markup. Bolt Depot's `Product-Details` pattern is the only
verified catalog-crawl demo source, so it's the default; a caller targeting a
different catalog site must pass its own pattern.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.ingestion.url_ingest import ingest_url
from app.ingestion.web_fetcher import FetchError
from app.schemas.product import ProductRecord

_DEFAULT_PRODUCT_URL_PATTERN = r"/Product-Details"  # Bolt Depot — the verified catalog-crawl demo source
_DEFAULT_MAX_PAGES = 20  # crawl pages, roughly 1 Firecrawl credit each
_DEFAULT_ENRICH_LIMIT = 10

_LINKS_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "catalog_links")

# `extract_product` is bound lazily (see `_resolve_extract_product()`), not
# imported at module load time. A top-level `from app.extraction.extractor
# import extract_product` here closes a cycle: app.extraction ->
# app.explainability -> app.ingestion.models -> (runs this package's
# __init__.py) -> this module -> app.extraction, while app.extraction is
# still mid-initialization. Kept as a module attribute (rather than a purely
# local import) so `test_catalog_crawler.py`'s
# `monkeypatch.setattr(catalog_crawler, "extract_product", ...)` still works.
extract_product = None


def _resolve_extract_product():
    global extract_product
    if extract_product is None:
        from app.extraction.extractor import extract_product as _extract_product

        extract_product = _extract_product
    return extract_product


class CatalogResult(BaseModel):
    """Output of `ingest_catalog_url()` — one page of enriched products plus
    a cursor so the caller's "load more" doesn't re-crawl.

    `enriched` holds `ProductRecord` — each discovered product page is parsed
    via `ingest_url()` then run through Phase 3's `extract_product()`.
    """

    catalog_url: str
    total_discovered: int
    enriched: list[ProductRecord] = Field(default_factory=list)
    failed_urls: list[str] = Field(default_factory=list)
    offset: int = 0
    has_more: bool = False


def _links_cache_path(catalog_url: str) -> str:
    url_hash = hashlib.sha256(catalog_url.encode("utf-8")).hexdigest()[:16]
    return os.path.join(_LINKS_CACHE_DIR, f"{url_hash}.json")


def _load_cached_links(catalog_url: str) -> list[str] | None:
    path = _links_cache_path(catalog_url)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None  # corrupt cache entry — treat as a miss, re-crawl


def _save_cached_links(catalog_url: str, links: list[str]) -> None:
    os.makedirs(_LINKS_CACHE_DIR, exist_ok=True)
    with open(_links_cache_path(catalog_url), "w", encoding="utf-8") as f:
        json.dump(links, f)


def discover_product_links(
    catalog_url: str,
    max_pages: int = _DEFAULT_MAX_PAGES,
    product_url_pattern: str = _DEFAULT_PRODUCT_URL_PATTERN,
) -> list[str]:
    """Crawl a listing page (and same-domain sibling/child category pages)
    and return every discovered link matching `product_url_pattern`.

    One Firecrawl crawl job for the whole discovery pass — `max_pages` bounds
    credit spend (roughly 1 credit per page crawled). Raises FetchError if
    FIRECRAWL_API_KEY isn't set or the crawl fails outright.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise FetchError(
            f"Cannot discover product links for '{catalog_url}' — "
            "FIRECRAWL_API_KEY is not set (catalog crawl requires it)."
        )

    from firecrawl import FirecrawlApp  # imported lazily: optional dep for callers that never crawl

    seed_path = urlparse(catalog_url).path
    include_paths = [f"^{re.escape(seed_path)}.*", product_url_pattern]

    app = FirecrawlApp(api_key=api_key)
    try:
        result = app.crawl_url(
            catalog_url,
            params={
                "limit": max_pages,
                "maxDepth": 2,
                "allowBackwardLinks": True,
                "includePaths": include_paths,
                "scrapeOptions": {"formats": ["links"]},
            },
        )
    except Exception as exc:  # Firecrawl SDK raises plain Exception on API errors
        raise FetchError(f"Firecrawl crawl of '{catalog_url}' failed: {exc}") from exc

    catalog_domain = urlparse(catalog_url).netloc
    pattern = re.compile(product_url_pattern)
    product_links: dict[str, None] = {}  # dict as an ordered set, insertion order preserved
    for page in result.get("data", []):
        for link in page.get("links", []):
            if urlparse(link).netloc != catalog_domain:
                continue
            if pattern.search(link):
                product_links[link] = None

    return list(product_links)


def ingest_catalog_url(
    catalog_url: str,
    limit: int = _DEFAULT_ENRICH_LIMIT,
    offset: int = 0,
) -> CatalogResult:
    """Discover product links from a catalog listing (once, cached), then
    enrich the `limit` links starting at `offset` via `ingest_url()`.

    A link that fails to ingest or extract (dead link, parse error, LLM
    failure) is recorded in `failed_urls` rather than aborting the whole
    batch — one bad product page shouldn't block the rest of a "load more"
    page.
    """
    extract = _resolve_extract_product()

    links = _load_cached_links(catalog_url)
    if links is None:
        links = discover_product_links(catalog_url)
        _save_cached_links(catalog_url, links)

    page_links = links[offset : offset + limit]
    enriched: list[ProductRecord] = []
    failed_urls: list[str] = []
    for link in page_links:
        try:
            doc = ingest_url(link)
            enriched.append(extract(doc))
        except Exception:  # dead link, parse error, or LLM/extraction failure — one bad page shouldn't sink the batch
            failed_urls.append(link)

    return CatalogResult(
        catalog_url=catalog_url,
        total_discovered=len(links),
        enriched=enriched,
        failed_urls=failed_urls,
        offset=offset,
        has_more=(offset + limit) < len(links),
    )