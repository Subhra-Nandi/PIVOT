"""Phase 2 tests for web ingestion: HTML parsing, fetch fallback, caching.

`parse_html` tests use hand-crafted HTML (no network). `fetch_html`/`ingest_url`
tests monkeypatch `httpx.get` and the Firecrawl call so the suite never makes
a real network request or spends a Firecrawl credit.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.ingestion import url_ingest, web_fetcher
from app.ingestion.models import BlockType, SourceFormat
from app.ingestion.web_fetcher import FetchError, fetch_html
from app.ingestion.web_parser import parse_html

JSON_LD_HTML = """
<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product", "name": "Widget", "sku": "W-1",
 "offers": {"@type": "Offer", "price": 9.99, "priceCurrency": "USD"}}
</script>
<h1>Overview</h1>
<p>A widget that widgets.</p>
<h2>Specs</h2>
<table>
<tr><th>Attribute</th><th>Value</th></tr>
<tr><td>Voltage</td><td>12V</td></tr>
</table>
</body></html>
"""

NO_JSON_LD_HTML = """
<html><body>
<h1>Plain Product</h1>
<p>No structured data here.</p>
</body></html>
"""

EMPTY_HTML = "<html><body></body></html>"


def test_parse_html_extracts_json_ld_product():
    doc = parse_html(JSON_LD_HTML, source_url="https://example.com/widget")
    assert doc.source_format == SourceFormat.WEBSITE
    assert doc.source_url == "https://example.com/widget"
    json_ld_blocks = [b for b in doc.blocks if b.section == "JSON-LD Product"]
    assert len(json_ld_blocks) == 1
    assert "name: Widget" in json_ld_blocks[0].text
    assert "offers.price: 9.99" in json_ld_blocks[0].text


def test_parse_html_extracts_table():
    doc = parse_html(JSON_LD_HTML, source_url="https://example.com/widget")
    tables = [b for b in doc.blocks if b.type == BlockType.TABLE]
    assert len(tables) == 1
    assert tables[0].table[0] == ["Attribute", "Value"]
    assert tables[0].table[1] == ["Voltage", "12V"]
    assert tables[0].section == "Specs"


def test_parse_html_tracks_section_from_headings():
    doc = parse_html(JSON_LD_HTML, source_url="https://example.com/widget")
    text_blocks = [b for b in doc.blocks if b.type == BlockType.TEXT and b.text == "A widget that widgets."]
    assert len(text_blocks) == 1
    assert text_blocks[0].section == "Overview"


def test_parse_html_warns_when_no_json_ld():
    doc = parse_html(NO_JSON_LD_HTML, source_url="https://example.com/plain")
    assert any("no JSON-LD Product data found" in w for w in doc.warnings)


def test_parse_html_warns_when_no_content():
    doc = parse_html(EMPTY_HTML, source_url="https://example.com/empty")
    assert doc.blocks == []
    assert any("no extractable text" in w for w in doc.warnings)


def test_fetch_html_uses_static_when_healthy(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, text="x" * 3000, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    html, method = fetch_html("https://example.com/ok")
    assert method == "static"
    assert len(html) == 3000


def test_fetch_html_falls_back_on_thin_response(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, text="thin", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(web_fetcher, "_fetch_via_firecrawl", lambda url: "<html>firecrawl content</html>")
    html, method = fetch_html("https://example.com/thin")
    assert method == "firecrawl"
    assert html == "<html>firecrawl content</html>"


def test_fetch_html_falls_back_on_403(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(403, text="x" * 5000, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(web_fetcher, "_fetch_via_firecrawl", lambda url: "<html>firecrawl content</html>")
    html, method = fetch_html("https://example.com/blocked")
    assert method == "firecrawl"


def test_fetch_html_raises_without_firecrawl_key(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(403, text="x" * 5000, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    with pytest.raises(FetchError):
        fetch_html("https://example.com/blocked")


def test_ingest_url_writes_and_reads_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(url_ingest, "_CACHE_DIR", str(tmp_path))
    call_count = {"n": 0}

    def fake_fetch_html(url):
        call_count["n"] += 1
        return JSON_LD_HTML, "static"

    monkeypatch.setattr(url_ingest, "fetch_html", fake_fetch_html)

    doc1 = url_ingest.ingest_url("https://example.com/cached", use_cache=True)
    doc2 = url_ingest.ingest_url("https://example.com/cached", use_cache=True)

    assert call_count["n"] == 1  # second call hit the cache, no re-fetch
    assert doc1.source_url == doc2.source_url == "https://example.com/cached"


def test_ingest_url_bypasses_cache_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(url_ingest, "_CACHE_DIR", str(tmp_path))
    call_count = {"n": 0}

    def fake_fetch_html(url):
        call_count["n"] += 1
        return JSON_LD_HTML, "static"

    monkeypatch.setattr(url_ingest, "fetch_html", fake_fetch_html)

    url_ingest.ingest_url("https://example.com/nocache", use_cache=False)
    url_ingest.ingest_url("https://example.com/nocache", use_cache=False)

    assert call_count["n"] == 2
