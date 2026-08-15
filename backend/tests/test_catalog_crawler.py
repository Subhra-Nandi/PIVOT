"""Phase 2 tests for catalog-URL crawl: discovery, enrichment, load-more cursor.

Firecrawl's crawl_url is monkeypatched with the actual response shape verified
live against Bolt Depot (see project memory) — no live network/API calls in
this suite, so it costs zero Firecrawl credits to run.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import pytest

from app.ingestion import catalog_crawler, url_ingest
from app.ingestion.catalog_crawler import CatalogResult, discover_product_links, ingest_catalog_url
from app.ingestion.models import IngestedDocument, SourceFormat
from app.ingestion.web_fetcher import FetchError
from app.schemas.product import ProductRecord

# Mirrors the real crawl_url("https://boltdepot.com/Hex_bolts", ...) response
# shape confirmed live: a list of scraped pages, each with sourceURL metadata
# and a `links` list that includes both product-detail pages and further
# sibling-category pages.
_FAKE_CRAWL_RESULT = {
    "success": True,
    "total": 3,
    "completed": 3,
    "creditsUsed": 3,
    "data": [
        {
            "metadata": {"sourceURL": "https://boltdepot.com/Hex_bolts"},
            "links": [
                "https://boltdepot.com/Hex_bolts_Stainless_steel_18-8",
                "https://boltdepot.com/Product-Details?product=54",
                "https://boltdepot.com/About",  # non-product link, must be filtered out
            ],
        },
        {
            "metadata": {"sourceURL": "https://boltdepot.com/Hex_bolts_Stainless_steel_18-8"},
            "links": [
                "https://boltdepot.com/Product-Details?product=3748",
                "https://boltdepot.com/Product-Details?product=9217",
            ],
        },
        {
            "metadata": {"sourceURL": "https://external-site.com/somewhere"},
            "links": [
                "https://external-site.com/Product-Details?product=999",  # off-domain, must be filtered out
            ],
        },
    ],
}


@pytest.fixture(autouse=True)
def _firecrawl_key(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")


@pytest.fixture(autouse=True)
def _stub_extraction(monkeypatch):
    """Phase 3's extract_product is out of scope for these tests — stub it to
    a trivial ProductRecord built from the IngestedDocument's URL so the
    catalog-crawl suite exercises discovery/pagination/caching without making
    any real LLM calls."""

    def fake_extract_product(doc, client=None):
        return ProductRecord(product_name=doc.source_url or doc.source_filename)

    monkeypatch.setattr(catalog_crawler, "extract_product", fake_extract_product)


@pytest.fixture()
def fake_firecrawl_app(monkeypatch):
    calls = []

    class FakeFirecrawlApp:
        def __init__(self, api_key):
            calls.append(api_key)

        def crawl_url(self, url, params=None, **kwargs):
            calls.append((url, params))
            return _FAKE_CRAWL_RESULT

    import firecrawl

    monkeypatch.setattr(firecrawl, "FirecrawlApp", FakeFirecrawlApp)
    return calls


def test_discover_product_links_filters_to_product_pattern_and_domain(fake_firecrawl_app):
    links = discover_product_links("https://boltdepot.com/Hex_bolts")
    assert links == [
        "https://boltdepot.com/Product-Details?product=54",
        "https://boltdepot.com/Product-Details?product=3748",
        "https://boltdepot.com/Product-Details?product=9217",
    ]


def test_discover_product_links_dedupes(monkeypatch, fake_firecrawl_app):
    import firecrawl

    dupe_result = dict(_FAKE_CRAWL_RESULT)
    dupe_result["data"] = _FAKE_CRAWL_RESULT["data"] + [_FAKE_CRAWL_RESULT["data"][0]]

    class FakeFirecrawlAppDupe:
        def __init__(self, api_key):
            pass

        def crawl_url(self, url, params=None, **kwargs):
            return dupe_result

    monkeypatch.setattr(firecrawl, "FirecrawlApp", FakeFirecrawlAppDupe)
    links = discover_product_links("https://boltdepot.com/Hex_bolts")
    assert len(links) == len(set(links))


def test_discover_product_links_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    with pytest.raises(FetchError):
        discover_product_links("https://boltdepot.com/Hex_bolts")


def test_ingest_catalog_url_enriches_and_paginates(tmp_path, monkeypatch, fake_firecrawl_app):
    monkeypatch.setattr(catalog_crawler, "_LINKS_CACHE_DIR", str(tmp_path))

    def fake_ingest_url(url, use_cache=True):
        return IngestedDocument(source_filename=url, source_format=SourceFormat.WEBSITE, source_url=url)

    monkeypatch.setattr(catalog_crawler, "ingest_url", fake_ingest_url)

    result = ingest_catalog_url("https://boltdepot.com/Hex_bolts", limit=2, offset=0)
    assert isinstance(result, CatalogResult)
    assert result.total_discovered == 3
    assert len(result.enriched) == 2
    assert result.has_more is True

    result2 = ingest_catalog_url("https://boltdepot.com/Hex_bolts", limit=2, offset=2)
    assert len(result2.enriched) == 1
    assert result2.has_more is False


def test_ingest_catalog_url_load_more_does_not_recrawl(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_crawler, "_LINKS_CACHE_DIR", str(tmp_path))

    crawl_calls = {"n": 0}

    def fake_discover(catalog_url, max_pages=20, product_url_pattern=r"/Product-Details"):
        crawl_calls["n"] += 1
        return [f"https://boltdepot.com/Product-Details?product={i}" for i in range(5)]

    monkeypatch.setattr(catalog_crawler, "discover_product_links", fake_discover)
    monkeypatch.setattr(
        catalog_crawler,
        "ingest_url",
        lambda url, use_cache=True: IngestedDocument(source_filename=url, source_format=SourceFormat.WEBSITE, source_url=url),
    )

    ingest_catalog_url("https://boltdepot.com/Hex_bolts", limit=2, offset=0)
    ingest_catalog_url("https://boltdepot.com/Hex_bolts", limit=2, offset=2)  # "load more"

    assert crawl_calls["n"] == 1  # second call reused the cached link list


def test_ingest_catalog_url_records_failed_links_without_aborting(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_crawler, "_LINKS_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        catalog_crawler,
        "discover_product_links",
        lambda *a, **k: ["https://boltdepot.com/Product-Details?product=1", "https://boltdepot.com/Product-Details?product=2"],
    )

    def flaky_ingest_url(url, use_cache=True):
        if "product=1" in url:
            raise FetchError("dead link")
        return IngestedDocument(source_filename=url, source_format=SourceFormat.WEBSITE, source_url=url)

    monkeypatch.setattr(catalog_crawler, "ingest_url", flaky_ingest_url)

    result = ingest_catalog_url("https://boltdepot.com/Hex_bolts", limit=10, offset=0)
    assert len(result.enriched) == 1
    assert result.failed_urls == ["https://boltdepot.com/Product-Details?product=1"]
