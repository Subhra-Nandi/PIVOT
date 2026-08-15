"""Intermediate ingestion format — the common output shape for every Phase 1
parser (PDF, DOCX, catalog).

Why an intermediate format at all: Phase 2 (website ingestion) and Phase 1
(document ingestion) are structurally very different sources, but Phase 3
(LLM extraction) should not need to know which one produced its input. Both
pipelines normalize into `IngestedDocument`, so Phase 3 only ever reads one
shape.

Design notes:
- Every `ContentBlock` carries a `page` (documents) so the Phase 5
  explainability layer can cite "document + page" the same way it will later
  cite "URL + snippet" for websites. DOCX has no native page concept, so page
  is left None there and `section` (heading text) is used instead — either
  one is enough to build a `SpecSource.reference`.
- Tables are kept as their own block type (rows of cells) rather than being
  flattened into text, because spec tables are usually the highest-value
  source for `Specification` extraction in Phase 3.
- `block_id` is stable and deterministic (source-relative index) so Phase 3
  can cite "block b0007" and Phase 5 can resolve it back to this document
  without re-parsing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceFormat(str, Enum):
    """Original file format that produced this document."""

    PDF = "pdf"
    DOCX = "docx"


class BlockType(str, Enum):
    """What kind of content a single `ContentBlock` holds."""

    HEADING = "heading"
    TEXT = "text"
    TABLE = "table"


class ContentBlock(BaseModel):
    """One unit of extracted content, with enough provenance to cite later.

    `page` and `section` are both optional because their availability is
    format-dependent (PDF has pages, not headings-as-sections by default;
    DOCX has headings, not pages) — Phase 3/5 should treat "at least one of
    page/section is set" as the citable anchor, not assume both.
    """

    block_id: str
    type: BlockType
    text: Optional[str] = None  # set for HEADING / TEXT
    table: Optional[list[list[Optional[str]]]] = None  # set for TABLE (rows x cells)
    page: Optional[int] = None  # 1-indexed; PDF only
    section: Optional[str] = None  # nearest preceding heading, if any


class IngestedDocument(BaseModel):
    """Normalized output of a Phase 1 parser — the thing Phase 3 consumes.

    `raw_text` is a flattened convenience view (all TEXT/HEADING blocks
    joined) for callers that just want plain text; `blocks` is the
    structured, citable view that the explainability layer actually needs.
    """

    source_filename: str
    source_format: SourceFormat
    page_count: Optional[int] = None  # None when the format has no pages (DOCX)
    blocks: list[ContentBlock] = Field(default_factory=list)
    raw_text: str = ""
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: list[str] = Field(default_factory=list)  # e.g. "page 3: no extractable text (scanned?)"

    @property
    def tables(self) -> list[ContentBlock]:
        """Convenience accessor for just the TABLE blocks."""
        return [b for b in self.blocks if b.type == BlockType.TABLE]
