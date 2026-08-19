"""Builds the 2-3 example records the Phase 7 demo UI ships with.

Per Phase 7's brief: "Use 2-3 reliable examples for the live demo rather
than risking an edge case failing on stage." This script runs the real
pipeline (catalog ingestion is genuinely zero-LLM; the document-extraction
example uses a canned LLM response via the same stub-client pattern
test_extraction.py uses) so it has zero network dependency and is safe to
re-run anytime. Output is static JSON the frontend reads directly — no
live backend/API needed for the demo.

Run from backend/: python scripts/build_demo_fixtures.py
Output: frontend/public/demo-data/*.json
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.commerce.mapping import map_to_all
from app.explainability import merge_records
from app.extraction.extractor import extract_product
from app.ingestion.catalog import ingest_catalog
from app.ingestion.models import BlockType, ContentBlock, IngestedDocument, SourceFormat
from app.schemas.product import (
    Commercial,
    Identifiers,
    Media,
    Price,
    Provenance,
    ProductRecord,
    Source,
    SourceType,
    SpecSource,
    Specification,
    SpecStatus,
)

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
_CATALOG_FIXTURE = os.path.join(_BACKEND_DIR, "fixtures", "catalogs", "demo_catalog.csv")
_OUTPUT_DIR = os.path.join(_BACKEND_DIR, "..", "frontend", "public", "demo-data")


class _StubClient:
    """Same mocking pattern as test_extraction.py — returns a canned
    response instead of calling a real LLM, so this script needs no API key
    and produces identical output every run."""

    def __init__(self, response: dict):
        self._response = json.dumps(response)

    def complete(self, prompt: str) -> str:
        return self._response


def _record_to_example(
    example_id: str,
    title: str,
    source_kind: str,
    raw_input_label: str,
    raw_input_text: str,
    record: ProductRecord,
) -> dict:
    return {
        "example_id": example_id,
        "title": title,
        "source_kind": source_kind,  # "catalog" | "document" | "merged"
        "raw_input": {"label": raw_input_label, "text": raw_input_text},
        "product_record": record.model_dump(mode="json"),
        "commerce": map_to_all(record),
    }


def _build_catalog_example() -> dict:
    """Example 1: a clean catalog row — every field EXTRACTED, high
    confidence, cited to "row N, column 'X'". Shows the simplest, most
    reliable path end-to-end."""
    result = ingest_catalog(_CATALOG_FIXTURE)
    record = result.records[0]  # "Panel Mount Terminal Block v1"

    with open(_CATALOG_FIXTURE, encoding="utf-8") as f:
        lines = f.readlines()
    raw_text = lines[0] + lines[1]

    return _record_to_example(
        example_id="catalog-terminal-block",
        title=record.product_name,
        source_kind="catalog",
        raw_input_label="demo_catalog.csv — header + row 1",
        raw_input_text=raw_text,
        record=record,
    )


def _build_document_example() -> dict:
    """Example 2: a PDF spec sheet run through LLM extraction (canned
    response — no real API call). Shows real page-cited snippets and one
    NEEDS_REVIEW field (low LLM confidence) alongside EXTRACTED ones."""
    doc = IngestedDocument(
        source_filename="acs37800_datasheet.pdf",
        source_format=SourceFormat.PDF,
        page_count=1,
        blocks=[
            ContentBlock(block_id="b0001", type=BlockType.HEADING, text="ACS37800 Power Meter Module", page=1),
            ContentBlock(
                block_id="b0002",
                type=BlockType.TEXT,
                text="Supply Voltage: 5V. Current Rating: 7.6A. IP Rating: IP65.",
                page=1,
            ),
            ContentBlock(
                block_id="b0003",
                type=BlockType.TEXT,
                text="Suitable for harsh factory floor environments with heavy dust exposure.",
                page=1,
            ),
        ],
        raw_text="ACS37800 Power Meter Module\nSupply Voltage: 5V. Current Rating: 7.6A. IP Rating: IP65.\n"
        "Suitable for harsh factory floor environments with heavy dust exposure.",
    )

    llm_response = {
        "product_name": "ACS37800 Power Meter Module",
        "brand": "SparkFun",
        "description": "Qwiic power monitoring breakout with current/voltage sensing.",
        "specifications": [
            {
                "attribute": "voltage_rating",
                "value": "5V",
                "unit": "V",
                "confidence": 0.92,
                "status": "extracted",
                "source": {"type": "document", "reference": "b0002"},
            },
            {
                "attribute": "current_rating",
                "value": "7.6A",
                "unit": "A",
                "confidence": 0.9,
                "status": "extracted",
                "source": {"type": "document", "reference": "b0002"},
            },
            {
                "attribute": "ip_rating",
                "value": "IP65",
                "confidence": 0.88,
                "status": "extracted",
                "source": {"type": "document", "reference": "b0002"},
            },
            {
                # Deliberately low-confidence: the model paraphrased loosely
                # rather than citing a stated value — a realistic example of
                # NEEDS_REVIEW earning its label.
                "attribute": "environmental_rating",
                "value": "Industrial (dust-resistant)",
                "confidence": 0.35,
                "status": "needs_review",
                "source": {"type": "document", "reference": "b0003"},
            },
        ],
    }
    client = _StubClient(llm_response)
    record = extract_product(doc, client=client)

    return _record_to_example(
        example_id="document-power-meter",
        title=record.product_name,
        source_kind="document",
        raw_input_label="acs37800_datasheet.pdf — page 1",
        raw_input_text=doc.raw_text,
        record=record,
    )


def _build_merged_conflict_example() -> dict:
    """Example 3: the same product from two sources that disagree on one
    attribute — demonstrates merge_records()'s conflict detection, the
    piece that finally populates Validation.conflicts."""
    sheet_record = ProductRecord(
        product_name="M8 Hex Bolt Zinc Plated",
        brand="Bolt Depot",
        identifiers=Identifiers(sku="BDM8-006", mpn="BD-M8HEX"),
        specifications=[
            Specification(
                attribute="tensile_strength",
                value="400",
                unit="MPa",
                confidence=0.9,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(
                    type=SourceType.DOCUMENT,
                    reference="src-1",
                    snippet="[Mechanical] Tensile strength: 400 MPa (Grade 8.8).",
                ),
            ),
        ],
        provenance=Provenance(
            sources_used=[Source(id="src-1", type=SourceType.DOCUMENT, reference="bolt_depot_spec_sheet.pdf", page=2)]
        ),
    )
    listing_record = ProductRecord(
        product_name="M8 Hex Bolt Zinc Plated",
        brand="Bolt Depot",
        media=Media(images=["https://example.com/m8-hex-bolt.jpg"]),
        commercial=Commercial(price=Price(value=10.71, currency="USD"), availability="in_stock"),
        specifications=[
            Specification(
                attribute="tensile_strength",
                value="600",
                unit="MPa",
                confidence=0.7,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(
                    type=SourceType.WEBSITE, reference="src-1", snippet="Tensile strength (per listing page): 600 MPa"
                ),
            ),
        ],
        provenance=Provenance(
            sources_used=[
                Source(id="src-1", type=SourceType.WEBSITE, reference="https://boltdepot.example.com/products/54")
            ]
        ),
    )

    merged = merge_records([sheet_record, listing_record])

    return _record_to_example(
        example_id="merged-hex-bolt-conflict",
        title=merged.product_name,
        source_kind="merged",
        raw_input_label="2 sources: bolt_depot_spec_sheet.pdf (p.2) + boltdepot.example.com listing",
        raw_input_text=(
            "Source A (PDF, page 2): Tensile strength: 400 MPa (Grade 8.8).\n\n"
            "Source B (website listing): Tensile strength (per listing page): 600 MPa"
        ),
        record=merged,
    )


def main() -> None:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    examples = [
        _build_catalog_example(),
        _build_document_example(),
        _build_merged_conflict_example(),
    ]

    index = []
    for example in examples:
        filename = f"{example['example_id']}.json"
        path = os.path.join(_OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(example, f, indent=2)
        index.append(
            {
                "example_id": example["example_id"],
                "title": example["title"],
                "source_kind": example["source_kind"],
                "file": filename,
            }
        )
        print(f"wrote {path}")

    index_path = os.path.join(_OUTPUT_DIR, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print(f"wrote {index_path}")


if __name__ == "__main__":
    main()
