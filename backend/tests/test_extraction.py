"""Phase 3 tests for IngestedDocument -> ProductRecord extraction.

`LLMClient.complete` is mocked with canned JSON — same mocking philosophy as
test_web_ingest.py's Firecrawl mocking — so this suite makes zero real LLM
calls.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import json

import pytest

from app.extraction.extractor import ExtractionError, extract_product
from app.ingestion.models import BlockType, ContentBlock, IngestedDocument, SourceFormat
from app.schemas.product import SourceType

_VALID_RECORD_JSON = {
    "product_name": "Widget 3000",
    "brand": "Acme",
    "specifications": [
        {
            "attribute": "Rated Voltage",  # alias — should normalize to voltage_rating
            "value": "12",
            "unit": "V",
            "confidence": 0.9,
            "status": "extracted",
            "source": {"type": "document", "reference": "b0002", "snippet": "12V"},
        }
    ],
}


def _doc(blocks=None, source_url=None) -> IngestedDocument:
    return IngestedDocument(
        source_filename="widget.pdf",
        source_format=SourceFormat.PDF,
        source_url=source_url,
        blocks=blocks
        or [
            ContentBlock(block_id="b0001", type=BlockType.HEADING, text="Widget 3000", page=1),
            ContentBlock(block_id="b0002", type=BlockType.TEXT, text="Rated Voltage: 12V", page=1),
        ],
    )


class _StubClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, prompt):
        self.calls.append(prompt)
        return self._responses.pop(0)


def test_extract_product_valid_response():
    client = _StubClient([json.dumps(_VALID_RECORD_JSON)])
    record = extract_product(_doc(), client=client)

    assert record.product_name == "Widget 3000"
    assert record.brand == "Acme"
    assert len(client.calls) == 1


def test_extract_product_normalizes_attribute_alias():
    client = _StubClient([json.dumps(_VALID_RECORD_JSON)])
    record = extract_product(_doc(), client=client)

    assert record.specifications[0].attribute == "voltage_rating"


def test_extract_product_fills_provenance_for_document():
    client = _StubClient([json.dumps(_VALID_RECORD_JSON)])
    record = extract_product(_doc(), client=client)

    assert len(record.provenance.sources_used) == 1
    source = record.provenance.sources_used[0]
    assert source.type == SourceType.DOCUMENT
    assert source.reference == "widget.pdf"
    assert record.provenance.extraction_timestamp is not None


def test_extract_product_fills_provenance_for_website():
    client = _StubClient([json.dumps(_VALID_RECORD_JSON)])
    doc = _doc(source_url="https://example.com/widget")
    record = extract_product(doc, client=client)

    source = record.provenance.sources_used[0]
    assert source.type == SourceType.WEBSITE
    assert source.reference == "https://example.com/widget"


def test_extract_product_strips_markdown_code_fences():
    fenced = "```json\n" + json.dumps(_VALID_RECORD_JSON) + "\n```"
    client = _StubClient([fenced])
    record = extract_product(_doc(), client=client)
    assert record.product_name == "Widget 3000"


def test_extract_product_retries_once_on_invalid_json():
    client = _StubClient(["not json at all", json.dumps(_VALID_RECORD_JSON)])
    record = extract_product(_doc(), client=client)

    assert record.product_name == "Widget 3000"
    assert len(client.calls) == 2
    assert "invalid" in client.calls[1].lower()


def test_extract_product_retries_once_on_validation_error():
    # Missing product_name (required) — fails ProductRecord validation.
    invalid = {"brand": "Acme"}
    client = _StubClient([json.dumps(invalid), json.dumps(_VALID_RECORD_JSON)])
    record = extract_product(_doc(), client=client)

    assert record.product_name == "Widget 3000"
    assert len(client.calls) == 2


def test_extract_product_raises_after_two_failures():
    client = _StubClient(["not json", "still not json"])
    with pytest.raises(ExtractionError):
        extract_product(_doc(), client=client)
    assert len(client.calls) == 2


def test_extract_product_unresolved_attribute_passes_through():
    record_json = {
        "product_name": "Mystery Part",
        "specifications": [
            {
                "attribute": "quantum_flux_capacity",  # not in the attribute dictionary
                "value": "42",
                "status": "needs_review",
            }
        ],
    }
    client = _StubClient([json.dumps(record_json)])
    record = extract_product(_doc(), client=client)
    assert record.specifications[0].attribute == "quantum_flux_capacity"
