"""Resolves each specification's raw block_id citation into a real `Source`
entry with page/section/snippet — closing the gap left by Phase 3.

The gap: `extract_product()`'s prompt (see `extraction/prompt.py`) instructs
the LLM to set `Specification.source.reference` to the *block_id* it pulled
a value from (e.g. "b0007"), but `extractor.py`'s `_fill_provenance()` only
ever writes a single generic `Source(id="src-1", ...)` for the whole
document — nothing that block_id resolves against. `SpecSource.reference` is
documented (`schemas/product.py`) to line up with a `Source.id` in
`Provenance.sources_used`; today, for LLM-extracted records, it doesn't.

`resolve_citations()` makes that true: one real `Source` per distinct cited
block (with its actual page and a snippet pulled from the real block text),
and every spec's reference rewritten to point at it.

Catalog-sourced records (`ingest_catalog()`) already do this correctly at
creation time — their `source.reference` already IS a real `Source.id`.
`resolve_citations()` detects that case (the reference already matches an
existing `Source.id`) and leaves those specs untouched, so it's always safe
to call on any `ProductRecord`, regardless of which pipeline produced it.
"""

from __future__ import annotations

import itertools

from app.explainability.snippets import make_snippet
from app.ingestion.models import IngestedDocument
from app.schemas.product import ProductRecord, Source, SourceType, SpecStatus


def resolve_citations(record: ProductRecord, doc: IngestedDocument) -> ProductRecord:
    """Rewrite block_id citations into real Source.id + snippet citations.

    Mutates and returns `record`. Idempotent: calling it twice on the same
    record is a no-op the second time, since every reference already matches
    an existing `Source.id` by then. Specs citing a block_id that doesn't
    exist in `doc.blocks` are left as-is rather than raised on — Phase 4's
    groundedness check already treats an unresolvable citation as a
    confidence penalty, so Phase 5 doesn't need to duplicate that as an error.
    """
    existing_ids = {s.id for s in record.provenance.sources_used}
    source_type = SourceType.WEBSITE if doc.source_url else SourceType.DOCUMENT
    reference = doc.source_url or doc.source_filename

    resolved_by_block: dict[str, Source] = {}
    taken_ids = set(existing_ids)
    id_counter = itertools.count(1)

    def _mint_id() -> str:
        for n in id_counter:
            candidate = f"src-{n}"
            if candidate not in taken_ids:
                taken_ids.add(candidate)
                return candidate
        raise AssertionError("unreachable")  # itertools.count(1) never exhausts

    for spec in record.specifications:
        if spec.source is None or spec.source.reference in existing_ids:
            continue  # no citation, or already a real Source.id (e.g. catalog path)

        block_id = spec.source.reference
        block = next((b for b in doc.blocks if b.block_id == block_id), None)
        if block is None:
            spec.status = SpecStatus.NEEDS_REVIEW
            spec.confidence = min(spec.confidence, 0.3)
            continue

        if block_id not in resolved_by_block:
            resolved_by_block[block_id] = Source(
                id=_mint_id(),
                type=source_type,
                reference=reference,
                page=block.page,
                retrieved_at=doc.ingested_at,
            )

        source = resolved_by_block[block_id]
        spec.source.reference = source.id
        spec.source.snippet = make_snippet(block, needle=spec.value)

    # Keep any source still cited (catalog's own, or one from a prior call);
    # drop the old single-placeholder Source only when something more
    # specific actually replaced it. If nothing resolved at all — a record
    # with no specifications, or every spec citing a hallucinated block_id
    # — the original source(s) still describe where this record came from
    # and must not be discarded: a record with zero traceable sources is
    # the one thing this pipeline can't afford to produce.
    if resolved_by_block:
        still_referenced = {s.source.reference for s in record.specifications if s.source}
        kept = [s for s in record.provenance.sources_used if s.id in still_referenced]
    else:
        kept = list(record.provenance.sources_used)

    record.provenance.sources_used = kept + list(resolved_by_block.values())

    return record
