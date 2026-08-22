"""Tests for the FastAPI layer (app/main.py).

The CSV/XLSX path is tested end-to-end for real, since `ingest_catalog()`
needs no LLM or network call — same reason the rest of the suite can test
catalog ingestion without mocking anything. The PDF/DOCX/URL paths (which
call `extract_product()`, and therefore an LLM provider) are tested only
for request validation and error surfacing here — they're already covered
end-to-end, with a stubbed LLM client, by test_extraction.py and
test_explainability.py; re-testing extract_product() itself through an
HTTP layer would just be a slower duplicate of those.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import app
from app import main as main_module
from app.ingestion.models import BlockType, ContentBlock, IngestedDocument, SourceFormat
from app.schemas.product import ProductRecord, SpecSource, Specification, SourceType

client = TestClient(app)

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_file_csv_returns_records_with_commerce_mapping():
    csv_path = os.path.join(_FIXTURES_DIR, "catalogs", "demo_catalog.csv")
    with open(csv_path, "rb") as f:
        response = client.post(
            "/extract/file",
            files={"file": ("demo_catalog.csv", f, "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_format"] == "csv"
    assert body["total_rows"] > 0
    assert len(body["items"]) > 0

    first = body["items"][0]
    assert "product_record" in first
    assert "commerce" in first
    assert set(first["commerce"]) == {"schema_org", "google_shopping", "industrial"}
    assert first["product_record"]["product_name"]


def test_extract_file_rejects_unsupported_extension():
    response = client.post(
        "/extract/file",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_extract_pdf_returns_source_blocks_and_metadata(tmp_path, monkeypatch):
    document = IngestedDocument(
        source_filename="datasheet.pdf",
        source_format=SourceFormat.PDF,
        page_count=2,
        blocks=[
            ContentBlock(block_id="b0000", type=BlockType.TEXT, text="Sensor", page=1),
            ContentBlock(block_id="b0001", type=BlockType.TEXT, text="Rated voltage: 24 V", page=2),
        ],
    )
    record = ProductRecord(
        product_name="Sensor",
        specifications=[Specification(
            attribute="voltage_rating", value="24 V", unit="V", source=SpecSource(
                type=SourceType.DOCUMENT, reference="src-1", snippet="Rated voltage: 24 V"
            )
        )],
    )
    pdf_path = tmp_path / "datasheet.pdf"
    pdf_path.write_bytes(b"placeholder")
    monkeypatch.setattr(main_module, "parse_pdf", lambda path: document)
    monkeypatch.setattr(main_module, "extract_product", lambda doc: record)

    with pdf_path.open("rb") as file:
        response = client.post("/extract/file", files={"file": ("datasheet.pdf", file, "application/pdf")})

    assert response.status_code == 200
    body = response.json()
    assert body["product_record"]["product_name"] == "Sensor"
    assert body["source"]["filename"] == "datasheet.pdf"
    assert body["source"]["page_count"] == 2
    assert [block["block_id"] for block in body["source"]["blocks"]] == ["b0000", "b0001"]
    assert body["source"]["blocks"][1]["page"] == 2
    assert body["source"]["blocks"][1]["text"] == "Rated voltage: 24 V"


def test_extract_url_surfaces_fetch_failure_as_502():
    # No cached fixture is seeded for this URL and it's not a real
    # reachable host in the test environment, so ingest_url() raises —
    # confirms the route turns that into a clean 502, not an unhandled 500.
    response = client.post(
        "/extract/url",
        json={"url": "https://this-domain-does-not-resolve.invalid/product/1"},
    )
    assert response.status_code == 502
    assert "Could not fetch" in response.json()["detail"]


def test_commerce_endpoint_maps_a_bare_record():
    minimal_record = {"product_name": "Test Widget", "brand": "Acme"}
    response = client.post("/commerce", json={"record": minimal_record})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"schema_org", "google_shopping", "industrial"}
    assert body["schema_org"]["document"]["name"] == "Test Widget"


def test_commerce_endpoint_rejects_invalid_record():
    response = client.post("/commerce", json={"record": {"brand": "Acme"}})
    # product_name is ProductRecord's only required field — omitting it
    # should fail FastAPI/Pydantic request validation (422), not reach
    # map_to_all() at all.
    assert response.status_code == 422
