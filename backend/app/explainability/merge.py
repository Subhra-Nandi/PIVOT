"""Merge ProductRecords for the same product from multiple sources,
detecting cross-source conflicts.

Closes a gap `validator.py` explicitly deferred: "`Validation.conflicts`
(cross-source disagreement) is intentionally left unpopulated for now —
every current pipeline path produces one record from one source, so there's
nothing to conflict-check yet." This module is what makes a real
multi-source case possible: run a PDF spec sheet and the manufacturer's
website through the pipeline separately, then merge the two records here.
Attributes every source agrees on merge cleanly; ones that disagree are
flagged `needs_review` and recorded as a `Conflict` — the explainability
story the challenge asks for, extended across sources instead of just within
one.
"""

from __future__ import annotations

from app.schemas.product import Conflict, ProductRecord, Specification, SpecStatus


def merge_records(records: list[ProductRecord]) -> ProductRecord:
    """Merge same-product records from multiple sources into one record.

    Uses the first record as the base for top-level fields (name, brand,
    category, commercial, etc.) — pass the most authoritative source first
    (e.g. a manufacturer spec-sheet PDF before a scraped listing page). All
    specifications from every record are pooled; attributes with disagreeing
    values across records are flagged `needs_review` on every contributing
    spec and recorded in `Validation.conflicts`. `overall_confidence` is
    recomputed as the mean across the merged specification set.

    Raises ValueError if `records` is empty.
    """
    if not records:
        raise ValueError("merge_records() requires at least one record")

    base = records[0]

    all_sources = []
    seen_source_ids: set[str] = set()
    for record in records:
        for source in record.provenance.sources_used:
            if source.id not in seen_source_ids:
                all_sources.append(source)
                seen_source_ids.add(source.id)

    all_specs: list[Specification] = [spec for record in records for spec in record.specifications]

    by_attribute: dict[str, list[Specification]] = {}
    for spec in all_specs:
        by_attribute.setdefault(spec.attribute, []).append(spec)

    conflicts: list[Conflict] = []
    for attribute, specs in by_attribute.items():
        distinct_values = {s.value.strip().lower() for s in specs}
        if len(distinct_values) <= 1:
            continue  # every contributing source agrees (or only one did)

        for spec in specs:
            spec.status = SpecStatus.NEEDS_REVIEW
        conflicts.append(
            Conflict(
                attribute=attribute,
                values=[s.value for s in specs],
                sources=[s.source.reference for s in specs if s.source],
            )
        )

    merged = base.model_copy(
        update={
            "specifications": all_specs,
            "provenance": base.provenance.model_copy(update={"sources_used": all_sources}),
            "validation": base.validation.model_copy(update={"conflicts": conflicts}),
        }
    )

    if merged.specifications:
        merged.validation.overall_confidence = round(
            sum(s.confidence for s in merged.specifications) / len(merged.specifications), 2
        )

    return merged
