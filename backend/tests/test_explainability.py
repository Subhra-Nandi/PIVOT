"""Phase 5 tests: citation resolution and multi-source merging.

`resolve_citations` is tested against a record shaped exactly like what
`extract_product()` produces today (spec.source.reference == a raw block_id,
provenance holding only the single `_fill_provenance()` placeholder) — see
`test_extraction.py`'s `_VALID_RECORD_JSON` for the same shape. No LLM or
network calls are needed since these functions operate purely on data
already produced by earlier phases.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import json

import pytest
from fpdf import FPDF

from app.explainability import make_snippet, merge_records, resolve_citations
from app.extraction.extractor import extract_product
from app.ingestion import BlockType, ingest_document
from app.ingestion.models import ContentBlock, IngestedDocument, SourceFormat
from app.schemas.product import (
    Provenance,
    ProductRecord,
    Source,
    SourceType,
    SpecSource,
    Specification,
    SpecStatus,
    Validation,
)


@pytest.fixture()
def spec_sheet_pdf(tmp_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 8, "Rated Voltage: 12V. Operating Temperature: -20C to 85C.")
    path = tmp_path / "spec_sheet.pdf"
    pdf.output(str(path))
    return str(path)


def _text_block_id(document):
    return next(b.block_id for b in document.blocks if b.type == BlockType.TEXT)


def _extractor_style_record(document, block_id, attribute="voltage_rating", value="12V"):
    """Builds a ProductRecord shaped exactly like extract_product() would
    return it *before* Phase 5 runs: spec.source.reference is a raw
    block_id, and provenance holds only the _fill_provenance() placeholder."""
    return ProductRecord(
        product_name="M8 Connector",
        specifications=[
            Specification(
                attribute=attribute,
                value=value,
                confidence=0.9,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(type=SourceType.DOCUMENT, reference=block_id, snippet=None),
            )
        ],
        provenance=Provenance(sources_used=[Source(id="src-1", type=SourceType.DOCUMENT, reference=document.source_filename)]),
    )


def test_resolves_block_id_into_real_source_id(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    block_id = _text_block_id(document)
    record = _extractor_style_record(document, block_id)

    resolve_citations(record, document)

    spec = record.specifications[0]
    resolved_ids = {s.id for s in record.provenance.sources_used}
    assert spec.source.reference in resolved_ids
    assert spec.source.reference != block_id


def test_snippet_is_populated_from_real_block_text(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    block_id = _text_block_id(document)
    record = _extractor_style_record(document, block_id)

    resolve_citations(record, document)

    assert record.specifications[0].source.snippet
    assert "12V" in record.specifications[0].source.snippet


def test_source_page_matches_cited_block(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    block_id = _text_block_id(document)
    record = _extractor_style_record(document, block_id)

    resolve_citations(record, document)

    matched = next(s for s in record.provenance.sources_used if s.id == record.specifications[0].source.reference)
    cited_block = next(b for b in document.blocks if b.block_id == block_id)
    assert matched.page == cited_block.page


def test_stale_placeholder_source_is_dropped_when_superseded(spec_sheet_pdf):
    """When resolution succeeds, the old single-placeholder Source (nothing
    points at it anymore) is dropped in favor of the more specific resolved
    one."""
    document = ingest_document(spec_sheet_pdf)
    block_id = _text_block_id(document)
    record = _extractor_style_record(document, block_id)

    resolve_citations(record, document)

    assert "src-1" not in {s.id for s in record.provenance.sources_used}
    assert len(record.provenance.sources_used) == 1


def test_citing_same_block_twice_dedupes_source(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    block_id = _text_block_id(document)
    record = _extractor_style_record(document, block_id)
    record.specifications.append(
        Specification(
            attribute="operating_temp",
            value="85C",
            confidence=0.9,
            status=SpecStatus.EXTRACTED,
            source=SpecSource(type=SourceType.DOCUMENT, reference=block_id),
        )
    )

    resolve_citations(record, document)

    assert len(record.provenance.sources_used) == 1


def test_idempotent_second_call_is_a_no_op(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    block_id = _text_block_id(document)
    record = _extractor_style_record(document, block_id)

    resolve_citations(record, document)
    first_pass_sources = list(record.provenance.sources_used)
    first_pass_reference = record.specifications[0].source.reference

    resolve_citations(record, document)

    assert record.provenance.sources_used == first_pass_sources
    assert record.specifications[0].source.reference == first_pass_reference


def test_catalog_style_record_is_left_untouched(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    record = ProductRecord(
        product_name="M8 Hex Bolt",
        specifications=[
            Specification(
                attribute="length",
                value="45",
                unit="mm",
                confidence=0.95,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(type=SourceType.DOCUMENT, reference="src-1", snippet="row 2, column 'Length'"),
            )
        ],
        provenance=Provenance(sources_used=[Source(id="src-1", type=SourceType.DOCUMENT, reference="catalog.csv")]),
    )

    resolve_citations(record, document)

    assert record.specifications[0].source.reference == "src-1"
    assert record.specifications[0].source.snippet == "row 2, column 'Length'"
    assert len(record.provenance.sources_used) == 1


def test_unresolvable_block_id_left_as_is(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    record = _extractor_style_record(document, "b9999")

    resolve_citations(record, document)

    assert record.specifications[0].source.reference == "b9999"
    assert record.specifications[0].status == SpecStatus.NEEDS_REVIEW
    assert record.specifications[0].confidence <= 0.3


def test_no_specs_does_not_wipe_provenance(spec_sheet_pdf):
    """Regression test (severe): a record with no specifications at all
    (the LLM extracted name/brand but no attributes) must not lose its
    only source. The old code computed "still referenced by a spec" from
    an empty specifications list, got an empty set, and overwrote
    provenance.sources_used with [] — a record with zero traceable sources
    is the one thing this pipeline can't afford to produce."""
    document = ingest_document(spec_sheet_pdf)
    record = ProductRecord(
        product_name="Widget",
        specifications=[],
        provenance=Provenance(
            sources_used=[Source(id="src-1", type=SourceType.DOCUMENT, reference=document.source_filename)]
        ),
    )

    resolve_citations(record, document)

    assert len(record.provenance.sources_used) == 1
    assert record.provenance.sources_used[0].reference == document.source_filename


def test_every_spec_unresolvable_does_not_wipe_provenance(spec_sheet_pdf):
    """Regression test (severe): same failure mode as above, triggered
    differently — every spec cites a block_id that doesn't exist in the
    document (a hallucinated citation). Nothing resolves, but the record's
    original source must still survive; it correctly stays unresolved
    rather than silently vanishing."""
    document = ingest_document(spec_sheet_pdf)
    record = _extractor_style_record(document, "b9999")

    resolve_citations(record, document)

    assert len(record.provenance.sources_used) == 1
    assert record.provenance.sources_used[0].id == "src-1"


def test_snippet_truncates_to_max_len(spec_sheet_pdf):
    document = ingest_document(spec_sheet_pdf)
    block = document.blocks[0]
    snippet = make_snippet(block, max_len=15)
    assert len(snippet) <= 15


def test_snippet_centers_matching_evidence():
    block = ContentBlock(
        block_id="b1", type=BlockType.TEXT,
        text="Specification | Rated Value | Body material | Stainless steel | Sensing face | PBT polymer",
    )
    snippet = make_snippet(block, max_len=40, needle="Stainless steel")
    assert "Stainless steel" in snippet
    assert len(snippet) <= 40


def test_snippet_falls_back_to_beginning_without_match():
    block = ContentBlock(block_id="b1", type=BlockType.TEXT, text="Alpha " * 50)
    snippet = make_snippet(block, max_len=20, needle="missing")
    assert snippet.startswith("Alpha")
    assert len(snippet) <= 20


def _record_with_spec(product_name, attribute, value, source_id, source_ref):
    return ProductRecord(
        product_name=product_name,
        specifications=[
            Specification(
                attribute=attribute,
                value=value,
                confidence=0.9,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(type=SourceType.DOCUMENT, reference=source_id),
            )
        ],
        provenance=Provenance(sources_used=[Source(id=source_id, type=SourceType.DOCUMENT, reference=source_ref)]),
        validation=Validation(overall_confidence=0.9),
    )


def test_merge_agreeing_sources_has_no_conflicts():
    a = _record_with_spec("M8 Connector", "voltage_rating", "12V", "src-1", "sheet.pdf")
    b = _record_with_spec("M8 Connector", "voltage_rating", "12V", "src-2", "site.html")

    merged = merge_records([a, b])

    assert merged.validation.conflicts == []
    assert all(s.status == SpecStatus.EXTRACTED for s in merged.specifications)
    assert len(merged.specifications) == 2
    assert len(merged.provenance.sources_used) == 2


def test_merge_disagreeing_sources_flags_conflict():
    a = _record_with_spec("M8 Connector", "voltage_rating", "12V", "src-1", "sheet.pdf")
    b = _record_with_spec("M8 Connector", "voltage_rating", "24V", "src-2", "site.html")

    merged = merge_records([a, b])

    assert len(merged.validation.conflicts) == 1
    conflict = merged.validation.conflicts[0]
    assert conflict.attribute == "voltage_rating"
    assert set(conflict.values) == {"12V", "24V"}
    assert set(conflict.sources) == {"src-1", "src-2"}
    assert all(s.status == SpecStatus.NEEDS_REVIEW for s in merged.specifications)


@pytest.mark.parametrize(
    "left,right,conflict",
    [("12 V", "12000 mV", False), ("12 V", "12 kV", True), ("24 V", "12000 mV", True)],
)
def test_merge_compares_compatible_units(left, right, conflict):
    a = _record_with_spec("Widget", "voltage_rating", left, "src-1", "a.pdf")
    b = _record_with_spec("Widget", "voltage_rating", right, "src-2", "b.pdf")
    merged = merge_records([a, b])
    assert bool(merged.validation.conflicts) is conflict


def test_merge_text_with_different_units_remains_conflicting():
    a = _record_with_spec("Widget", "finish", "10", "src-1", "a.pdf")
    b = _record_with_spec("Widget", "finish", "10", "src-2", "b.pdf")
    a.specifications[0].unit = "mm"
    b.specifications[0].unit = "in"
    merged = merge_records([a, b])
    assert merged.validation.conflicts


def test_merge_recomputes_overall_confidence():
    a = _record_with_spec("Widget", "voltage_rating", "12V", "src-1", "sheet.pdf")
    a.specifications[0].confidence = 0.8
    b = _record_with_spec("Widget", "current_rating", "2A", "src-2", "site.html")
    b.specifications[0].confidence = 0.6

    merged = merge_records([a, b])

    assert merged.validation.overall_confidence == pytest.approx(0.7)


def test_merge_uses_first_record_as_base_for_top_level_fields():
    a = _record_with_spec("M8 Connector", "voltage_rating", "12V", "src-1", "sheet.pdf")
    a.brand = "Acme"
    b = _record_with_spec("M8 Connector (listing)", "voltage_rating", "12V", "src-2", "site.html")

    merged = merge_records([a, b])

    assert merged.product_name == "M8 Connector"
    assert merged.brand == "Acme"


def test_merge_empty_list_raises():
    with pytest.raises(ValueError):
        merge_records([])


def test_merge_does_not_drop_sources_with_colliding_local_ids():
    """Regression test: every pipeline path (ingest_catalog, resolve_citations)
    numbers a record's own Source.ids starting from "src-1", so two records
    reusing the same local id is the normal case, not an edge case. Merging
    must not silently drop one source just because two records happened to
    number their sources the same way."""
    a = _record_with_spec("Widget", "voltage_rating", "12V", "src-1", "sheet.pdf")
    b = _record_with_spec("Widget", "current_rating", "2A", "src-1", "listing.html")

    merged = merge_records([a, b])

    assert len(merged.provenance.sources_used) == 2
    references = {s.reference for s in merged.provenance.sources_used}
    assert references == {"sheet.pdf", "listing.html"}
    resolved_ids = {s.id for s in merged.provenance.sources_used}
    assert all(spec.source.reference in resolved_ids for spec in merged.specifications)


def test_merge_does_not_mutate_input_records():
    a = _record_with_spec("Widget", "voltage_rating", "12V", "src-1", "sheet.pdf")
    b = _record_with_spec("Widget", "voltage_rating", "24V", "src-1", "listing.html")

    merge_records([a, b])

    assert a.provenance.sources_used[0].id == "src-1"
    assert a.specifications[0].status == SpecStatus.EXTRACTED


class _StubClient:
    def __init__(self, response):
        self._response = response

    def complete(self, prompt):
        return self._response


def test_extract_product_returns_resolved_citation_not_raw_block_id():
    """Regression test for the gap Phase 5 closes: before this, a record
    fresh out of extract_product() had spec.source.reference set to a raw
    block_id that didn't match anything in provenance.sources_used."""
    doc = IngestedDocument(
        source_filename="widget.pdf",
        source_format=SourceFormat.PDF,
        blocks=[
            ContentBlock(block_id="b0001", type=BlockType.HEADING, text="Widget 3000", page=1),
            ContentBlock(block_id="b0002", type=BlockType.TEXT, text="Rated Voltage: 12V", page=1),
        ],
    )
    llm_response = {
        "product_name": "Widget 3000",
        "specifications": [
            {
                "attribute": "voltage_rating",
                "value": "12V",
                "unit": "V",
                "confidence": 0.9,
                "status": "extracted",
                "source": {"type": "document", "reference": "b0002"},
            }
        ],
    }
    client = _StubClient(json.dumps(llm_response))

    record = extract_product(doc, client=client)

    spec = record.specifications[0]
    resolved_ids = {s.id for s in record.provenance.sources_used}
    assert spec.source.reference in resolved_ids
    assert spec.source.reference != "b0002"
    assert spec.source.snippet and "12V" in spec.source.snippet
    assert spec.status == SpecStatus.EXTRACTED
    assert spec.confidence > 0.5
