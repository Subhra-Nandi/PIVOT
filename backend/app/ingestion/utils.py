"""Small shared helpers for Phase 1 parsers.

Kept separate from the parsers themselves so pdf_parser.py and docx_parser.py
stay format-specific and easy for a teammate to extend (e.g. adding XLSX
catalog support later) without touching this file.
"""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace/newlines without destroying paragraph
    breaks entirely — extractors tend to emit ragged spacing."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def make_block_id(index: int) -> str:
    """Deterministic, sortable block id: b0000, b0001, ..."""
    return f"b{index:04d}"


def table_to_text(rows: list[list[str | None]]) -> str:
    """Flatten a table into a plain-text fallback for `raw_text`.

    Not used for the structured `table` field — only for the convenience
    `raw_text` view, so a caller doing a naive text search still finds
    table content.
    """
    lines = []
    for row in rows:
        cells = [c.strip() if c else "" for c in row]
        lines.append(" | ".join(cells))
    return "\n".join(lines)
