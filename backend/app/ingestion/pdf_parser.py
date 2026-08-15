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


def _outside_bboxes(obj, bboxes) -> bool:
    """True if a pdfplumber object's midpoint falls outside every table bbox.

    Used to drop table cell text from the page-level text pass, so a table's
    content lives in exactly one block (TABLE) rather than being duplicated
    into a TEXT block as well — pdfplumber's extract_text() includes table
    text by default.
    """
    h_mid = (obj["x0"] + obj["x1"]) / 2
    v_mid = (obj["top"] + obj["bottom"]) / 2
    for x0, top, x1, bottom in bboxes:
        if x0 <= h_mid < x1 and top <= v_mid < bottom:
            return False
    return True


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
                    found_tables = page.find_tables()
                except Exception as exc:
                    found_tables = []
                    warnings.append(f"page {page_number}: table detection failed ({exc})")

                # Collect this page's content with its vertical position
                # (pdfplumber `top` grows downward) so blocks are emitted in
                # reading order rather than "all tables, then text" — matching
                # the order-preservation the DOCX parser already gives.
                page_items = []  # list of (top, BlockType, payload)
                table_bboxes = []
                for found in found_tables:
                    table_rows = found.extract()
                    if not table_rows:
                        continue
                    table_bboxes.append(found.bbox)
                    page_items.append((found.bbox[1], BlockType.TABLE, table_rows))

                # Page text EXCLUDING detected table regions, so a table's cell
                # content isn't duplicated into a TEXT block as well —
                # pdfplumber's extract_text() includes table text by default.
                text_source = (
                    page.filter(lambda obj, _bb=table_bboxes: _outside_bboxes(obj, _bb))
                    if table_bboxes
                    else page
                )
                text = normalize_whitespace(text_source.extract_text() or "")
                if text:
                    text_top = min((c["top"] for c in text_source.chars), default=0.0)
                    page_items.append((text_top, BlockType.TEXT, text))

                page_items.sort(key=lambda item: item[0])
                for _top, block_type, payload in page_items:
                    page_had_content = True
                    if block_type == BlockType.TABLE:
                        blocks.append(
                            ContentBlock(
                                block_id=make_block_id(block_index),
                                type=BlockType.TABLE,
                                table=payload,
                                page=page_number,
                            )
                        )
                        raw_text_parts.append(table_to_text(payload))
                    else:
                        blocks.append(
                            ContentBlock(
                                block_id=make_block_id(block_index),
                                type=BlockType.TEXT,
                                text=payload,
                                page=page_number,
                            )
                        )
                        raw_text_parts.append(payload)
                    block_index += 1

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
