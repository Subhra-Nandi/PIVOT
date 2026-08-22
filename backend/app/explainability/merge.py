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

import itertools
import re
from app.validation.units import convert_to_base

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

    Does not mutate its inputs — each record is deep-copied before any
    remapping, so callers can keep using their original `ProductRecord`
    objects unmodified after merging.

    Raises ValueError if `records` is empty.
    """
    if not records:
        raise ValueError("merge_records() requires at least one record")

    records = [r.model_copy(deep=True) for r in records]
    base = records[0]

    all_sources = []
    all_specs: list[Specification] = []
    next_id = itertools.count(1)

    for record in records:
        # Each record's Source.id values were minted independently by
        # whichever pipeline produced it, so different records commonly
        # reuse the same local id ("src-1") for genuinely different
        # sources — every pipeline path starts numbering from 1. Remap
        # every source to a fresh, globally-unique id before pooling, and
        # rewrite each spec's citation to match — merging by raw id would
        # silently collide and drop one source's citations (confirmed: a
        # record citing "src-1" from a PDF and another citing "src-1" from
        # a website merge into a single source, losing the website one).
        id_map: dict[str, str] = {}
        for source in record.provenance.sources_used:
            new_id = f"src-{next(next_id)}"
            id_map[source.id] = new_id
            source.id = new_id
            all_sources.append(source)

        for spec in record.specifications:
            if spec.source is not None and spec.source.reference in id_map:
                spec.source.reference = id_map[spec.source.reference]
            all_specs.append(spec)

    by_attribute: dict[str, list[Specification]] = {}
    for spec in all_specs:
        by_attribute.setdefault(spec.attribute, []).append(spec)

    conflicts: list[Conflict] = []
    for attribute, specs in by_attribute.items():
        def comparable(spec):
            match = re.match(r"^\s*([-+]?\d+(?:\.\d+)?)\s*([^\d\s].*)?\s*$", spec.value)
            unit = spec.unit or (match.group(2).strip() if match and match.group(2) else None)
            if match and unit:
                converted = convert_to_base(float(match.group(1)), unit)
                if converted:
                    return (converted[1], round(converted[0], 9))
            return (spec.value.strip().lower(), (unit or "").strip().lower())
        distinct_values = {comparable(s) for s in specs}
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
