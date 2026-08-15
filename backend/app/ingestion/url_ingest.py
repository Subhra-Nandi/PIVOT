"""`ingest_url()` — the single-product-URL entrypoint for Phase 2.

Fetch (static-first, Firecrawl fallback) -> parse -> cache. Caching matters
for two reasons: demo day shouldn't ride on live network or Firecrawl credits,
and repeated runs against the same URL during development shouldn't re-fetch.

Cache is a JSON file per URL under `backend/.cache/web/` (gitignored — see
`.gitignore`'s `__pycache__`-style local-state entries; this directory is
runtime-only, not a fixture). Demo fixtures are a separate, committed
concern (`backend/fixtures/web/`) built explicitly, not populated by this
cache.
"""

from __future__ import annotations

import hashlib
import json
import os

from app.ingestion.models import IngestedDocument
from app.ingestion.web_fetcher import fetch_html
from app.ingestion.web_parser import parse_html

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "web")


def _cache_path(url: str) -> str:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return os.path.join(_CACHE_DIR, f"{url_hash}.json")


def _load_cache(url: str) -> IngestedDocument | None:
    path = _cache_path(url)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return IngestedDocument.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None  # corrupt cache entry — treat as a miss, re-fetch


def _save_cache(url: str, document: IngestedDocument) -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = _cache_path(url)
    with open(path, "w", encoding="utf-8") as f:
        f.write(document.model_dump_json())


def ingest_url(url: str, use_cache: bool = True) -> IngestedDocument:
    """Fetch and parse a single product page into an `IngestedDocument`.

    Static fetch is tried first; Firecrawl is used only if the static fetch
    fails or returns thin content. Set `use_cache=False` to force a live
    re-fetch (e.g. a "refresh" action in the UI).
    """
    if use_cache:
        cached = _load_cache(url)
        if cached is not None:
            return cached

    html, _fetch_method = fetch_html(url)
    document = parse_html(html, source_url=url)

    if use_cache:
        _save_cache(url, document)

    return document


def seed_cache_from_fixture(url: str, fixture_path: str) -> IngestedDocument:
    """Parse a committed HTML fixture and write it into the runtime cache
    under `url`, without ever touching the network.

    Used by `scripts/seed_web_cache.py` to pre-warm the cache before a demo
    from `backend/fixtures/web/*.html`, so `ingest_url()` hits a cache entry
    on stage even if the venue has no network or Firecrawl is down.
    """
    with open(fixture_path, encoding="utf-8") as f:
        html = f.read()
    document = parse_html(html, source_url=url)
    _save_cache(url, document)
    return document
