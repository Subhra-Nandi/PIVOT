"""IngestedDocument -> ProductRecord via schema-guided LLM extraction.

This is the piece Phase 2 left as a placeholder: `CatalogResult.enriched`
held `IngestedDocument` because nothing could turn a scraped/parsed page into
a `ProductRecord`. `extract_product()` is that conversion.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from pydantic import ValidationError

from app.extraction.prompt import build_extraction_prompt
from app.ingestion.models import IngestedDocument
from app.llm import get_default_client
from app.llm.base import LLMClient
from app.schemas.attributes import resolve_attribute
from app.schemas.product import ProductRecord, Source, SourceType
from app.validation import validate_record

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class ExtractionError(RuntimeError):
    """Raised when the LLM's response can't be turned into a valid
    ProductRecord even after one retry."""


def _strip_code_fences(raw: str) -> str:
    """Models often wrap JSON in ```json blocks despite instructions not to —
    strip them defensively rather than failing the parse over formatting."""
    return _CODE_FENCE_PATTERN.sub("", raw.strip()).strip()


def _parse_and_validate(raw: str) -> ProductRecord:
    cleaned = _strip_code_fences(raw)
    data = json.loads(cleaned)  # raises json.JSONDecodeError on failure
    return ProductRecord.model_validate(data)  # raises ValidationError on failure


def _normalize_attributes(record: ProductRecord) -> None:
    """Resolves each spec's attribute name to its canonical form where known.
    Unknown attributes pass through unchanged — same contract as
    `catalog.py`'s column mapping: unresolved is valid, just lower-confidence
    downstream, not an error."""
    for spec in record.specifications:
        resolved = resolve_attribute(spec.attribute)
        if resolved is not None:
            spec.attribute = resolved.attribute


def _fill_provenance(record: ProductRecord, doc: IngestedDocument) -> None:
    source_type = SourceType.WEBSITE if doc.source_url else SourceType.DOCUMENT
    reference = doc.source_url or doc.source_filename
    record.provenance.sources_used = [
        Source(id="src-1", type=source_type, reference=reference)
    ]
    record.provenance.extraction_timestamp = datetime.now(timezone.utc)


def extract_product(doc: IngestedDocument, client: LLMClient | None = None) -> ProductRecord:
    """Extracts a ProductRecord from an IngestedDocument's content blocks.

    Calls `client.complete()` (default: the Gemini -> Groq -> GitHub Models
    fallback chain) with a schema-guided prompt, validates the response, and
    retries once — re-prompting with the validation error — before raising
    ExtractionError.
    """
    client = client or get_default_client()
    prompt = build_extraction_prompt(doc)
    raw = client.complete(prompt)

    try:
        record = _parse_and_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        retry_prompt = (
            f"{prompt}\n\nYour previous response was invalid: {exc}. "
            "Return corrected strict JSON only, matching the schema exactly."
        )
        raw2 = client.complete(retry_prompt)
        try:
            record = _parse_and_validate(raw2)
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise ExtractionError(
                f"LLM response failed validation twice for '{doc.source_filename}': {exc2}"
            ) from exc2

    _normalize_attributes(record)
    _fill_provenance(record, doc)
    validate_record(record, blocks=doc.blocks)
    return record
