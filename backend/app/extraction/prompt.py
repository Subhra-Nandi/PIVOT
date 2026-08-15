"""Builds the extraction prompt handed to `LLMClient.complete()`.

Schema-guided per Phase 0's design: the model targets `ProductRecord`'s real
JSON schema rather than free-form generation. Each content block keeps its
`block_id`/`page`/`section` so the model can cite where a value came from —
without that, Phase 5's explainability layer would have nothing to point at.
"""

from __future__ import annotations

import json

from app.ingestion.models import IngestedDocument
from app.schemas.attributes import ATTRIBUTE_DICTIONARY
from app.schemas.product import ProductRecord

_INSTRUCTIONS = """\
You are extracting a structured product record from source content for an \
industrial commerce catalog.

Return ONLY a single JSON object matching the schema below. No markdown code \
fences, no prose, no explanation — JSON only.

Rules:
- Only use information present in the source content below. Never invent or \
guess a value.
- If a field is not present in the source, set it to null (or an empty list/ \
array where the schema expects one) rather than guessing.
- For every entry in "specifications", set "source.reference" to the \
block_id (e.g. "b0007") of the content block the value came from. If the \
value came from a table, use that table block's block_id.
- Set each specification's "status" to "extracted" if the value is stated \
directly in the source, or "inferred" if you derived/normalized it (e.g. \
converting units). Use "needs_review" if you are unsure or sources conflict.
- Prefer these canonical attribute names when applicable (use your own \
name if none fit): {canonical_names}
- "product_name" is the only required field — always set it.
"""


def _render_blocks(doc: IngestedDocument) -> str:
    lines: list[str] = []
    for block in doc.blocks:
        location = []
        if block.page is not None:
            location.append(f"page {block.page}")
        if block.section:
            location.append(f"section '{block.section}'")
        location_str = f" ({', '.join(location)})" if location else ""

        if block.type.value == "table" and block.table:
            rows = "\n".join(" | ".join(cell or "" for cell in row) for row in block.table)
            lines.append(f"[{block.block_id}] TABLE{location_str}:\n{rows}")
        elif block.text:
            lines.append(f"[{block.block_id}] {block.type.value.upper()}{location_str}: {block.text}")
    return "\n\n".join(lines)


def build_extraction_prompt(doc: IngestedDocument) -> str:
    """Renders the full prompt: instructions + target schema + source blocks."""
    canonical_names = ", ".join(sorted(ATTRIBUTE_DICTIONARY.keys()))
    instructions = _INSTRUCTIONS.format(canonical_names=canonical_names)
    schema_json = json.dumps(ProductRecord.model_json_schema(), indent=2)
    blocks_text = _render_blocks(doc)

    source_label = doc.source_url or doc.source_filename
    return (
        f"{instructions}\n"
        f"Target JSON schema:\n{schema_json}\n\n"
        f"Source: {source_label}\n"
        f"Content blocks:\n{blocks_text}\n"
    )
