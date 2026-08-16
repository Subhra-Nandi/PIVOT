"""Build a short, citable snippet from a `ContentBlock`.

Used to populate `SpecSource.snippet` with the *actual* source text, rather
than whatever the LLM freely wrote there (Phase 3's prompt never asks for a
snippet at all — see `extraction/prompt.py`'s instructions — so today it's
either empty or an unverified guess). Grounding the snippet in the real
block text is what makes a citation trustworthy to click through and check.
"""

from __future__ import annotations

from app.ingestion.models import BlockType, ContentBlock

DEFAULT_SNIPPET_LEN = 200


def make_snippet(block: ContentBlock, max_len: int = DEFAULT_SNIPPET_LEN) -> str:
    """Flatten a block's content into a single-line, citable snippet.

    Tables are flattened cell-by-cell; text/heading blocks are used as-is.
    When the block carries a `section` (DOCX headings, web `<h1>`-`<h6>`),
    it's prefixed in brackets — `Source.page` alone can't capture that, so
    the snippet is where section context survives into the citation.
    """
    if block.type == BlockType.TABLE and block.table:
        text = " | ".join(cell for row in block.table for cell in row if cell)
    else:
        text = block.text or ""

    text = " ".join(text.split())
    if block.section:
        text = f"[{block.section}] {text}"
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text
