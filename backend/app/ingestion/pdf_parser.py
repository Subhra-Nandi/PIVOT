"""PDF parsing — Phase 1.

Uses pdfplumber because it gives us both text and tables per page with
minimal setup, and page numbers fall out naturally (pdfplumber pages are
already 0-indexed in order, we just +1 for a human-facing page number).

Scanned/image-only PDFs are explicitly out of scope here (pdfplumber can't
extract text that isn't there) — we detect the empty-page case and record a
warning rather than silently returning nothing, so Phase 8's "stress-test a
scanned PDF" step has something to point at. OCR fallback is a documented
future extension, not built here.
"""

from __future__ import annotations

import os

import pdfplumber

from app.ingestion.models import BlockType, ContentBlock, IngestedDocument, SourceFormat
from app.ingestion.utils import make_block_id, normalize_whitespace, table_to_text


def parse_pdf(path: str) -> IngestedDocument:
    """Parse a PDF file into an `IngestedDocument`.

    Raises FileNotFoundError if `path` doesn't exist, and ValueError if the
    file can't be opened as a PDF at all (e.g. corrupted / wrong format).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such file: {path}")

    filename = os.path.basename(path)
    blocks: list[ContentBlock] = []
    raw_text_parts: list[str] = []
    warnings: list[str] = []
    block_index = 0

    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)

            for page_number, page in enumerate(pdf.pages, start=1):
                page_had_content = False

                try:
                    raw_tables = page.extract_tables() or []
                except Exception as exc:
                    raw_tables = []
                    warnings.append(f"page {page_number}: table extraction failed ({exc})")

                for table_rows in raw_tables:
                    if not table_rows:
                        continue
                    page_had_content = True
                    blocks.append(
                        ContentBlock(
                            block_id=make_block_id(block_index),
                            type=BlockType.TABLE,
                            table=table_rows,
                            page=page_number,
                        )
                    )
                    block_index += 1
                    raw_text_parts.append(table_to_text(table_rows))

                text = page.extract_text() or ""
                text = normalize_whitespace(text)
                if text:
                    page_had_content = True
                    blocks.append(
                        ContentBlock(
                            block_id=make_block_id(block_index),
                            type=BlockType.TEXT,
                            text=text,
                            page=page_number,
                        )
                    )
                    block_index += 1
                    raw_text_parts.append(text)

                if not page_had_content:
                    warnings.append(
                        f"page {page_number}: no extractable text or tables "
                        "(likely scanned/image-only — OCR not implemented)"
                    )
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not parse '{filename}' as a PDF: {exc}") from exc

    return IngestedDocument(
        source_filename=filename,
        source_format=SourceFormat.PDF,
        page_count=page_count,
        blocks=blocks,
        raw_text="\n\n".join(raw_text_parts),
        warnings=warnings,
    )
