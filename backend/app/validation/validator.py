"""Entrypoint for Phase 4: computes real per-field confidence and rolls it up
into `ProductRecord.validation.overall_confidence`.

Replaces the flat placeholders written upstream (catalog.py's hardcoded 0.95,
the Phase 3 extractor's un-adjusted LLM-claimed confidence) with a value
actually earned from the attribute-dictionary rule check plus, when source
blocks are available, a groundedness check.

Formula is intentionally simple and inspectable (named constants below, not
learned weights) so "why did this field score 0.42" has a one-line answer —
useful for explaining the validation story to judges.
"""

from __future__ import annotations

from app.ingestion.models import ContentBlock
from app.schemas.product import ProductRecord, SourceType, SpecStatus
from app.validation.checks import CheckOutcome, run_attribute_check
from app.validation.groundedness import check_groundedness, find_block

# Starting point before any check adjusts it — reflects how the value was
# obtained, independent of whether it turns out to check out.
_BASE_BY_STATUS: dict[SpecStatus, float] = {
    SpecStatus.EXTRACTED: 0.85,
    SpecStatus.INFERRED: 0.6,
    SpecStatus.NEEDS_REVIEW: 0.3,
}

# Document sources (spec sheets, catalogs) score higher trust than scraped
# websites, per Phase 0's design.
_SOURCE_TRUST: dict[SourceType, float] = {
    SourceType.DOCUMENT: 1.0,
    SourceType.WEBSITE: 0.85,
}

_CHECK_PASS_BOOST = 0.10
_CHECK_FAIL_PENALTY = 0.45
_CHECK_UNVERIFIABLE_PENALTY = 0.05
_UNGROUNDED_PENALTY = 0.45


def _score_spec(spec, blocks: list[ContentBlock] | None) -> float:
    # A missing source is a data gap, not a signal of low trust — default to
    # neutral (1.0) rather than assuming website-level distrust.
    source_trust = _SOURCE_TRUST.get(spec.source.type, 1.0) if spec.source else 1.0
    confidence = _BASE_BY_STATUS.get(spec.status, 0.5) * source_trust

    outcome, _reason = run_attribute_check(spec)
    if outcome == CheckOutcome.PASS:
        confidence += _CHECK_PASS_BOOST
    elif outcome == CheckOutcome.FAIL:
        confidence -= _CHECK_FAIL_PENALTY
        spec.status = SpecStatus.NEEDS_REVIEW
    else:  # UNVERIFIABLE
        confidence -= _CHECK_UNVERIFIABLE_PENALTY

    if blocks is not None and spec.source is not None:
        block = find_block(blocks, spec.source.reference)
        if block is None:
            confidence -= _UNGROUNDED_PENALTY
            spec.status = SpecStatus.NEEDS_REVIEW
        elif not check_groundedness(spec.value, block):
            confidence -= _UNGROUNDED_PENALTY
            spec.status = SpecStatus.NEEDS_REVIEW

    return max(0.0, min(1.0, confidence))


def validate_record(record: ProductRecord, blocks: list[ContentBlock] | None = None) -> ProductRecord:
    """Recomputes `Specification.confidence`/`status` for every spec on
    `record`, and rolls the result up into `record.validation.overall_confidence`.

    `blocks` — the source `IngestedDocument.blocks`, when available — enables
    the groundedness check (a spec's cited `block_id` must actually contain
    its value). Omit for CSV/XLSX-sourced records, where a spec's value *is*
    its source cell and there's nothing further to check.

    Mutates and returns `record`.
    """
    for spec in record.specifications:
        spec.confidence = _score_spec(spec, blocks)

    if record.specifications:
        record.validation.overall_confidence = round(
            sum(s.confidence for s in record.specifications) / len(record.specifications), 2
        )

    return record
