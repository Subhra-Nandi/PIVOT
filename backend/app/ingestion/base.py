"""Single entrypoint for Phase 1 ingestion — dispatches by file extension.

This is the function everything else (Phase 3 extraction, a future FastAPI
`/extract` endpoint, ad-hoc scripts) should import, rather than reaching into
`pdf_parser` or `docx_parser` directly. Keeping one dispatch point means
adding a new format (e.g. XLSX catalogs) later only touches this file plus a
new `<format>_parser.py` — nothing that already imports `ingest_document`
needs to change.

NOTE: `ingest_document()` returns one of two different shapes depending on
input format:
- PDF/DOCX -> `IngestedDocument` (unstructured content, still needs Phase 3
  LLM extraction to become a `ProductRecord`).
- CSV/XLSX/XLSM -> `CatalogIngestResult` (already-structured `ProductRecord`s,
  Phase 3 is skipped entirely — see `catalog.py`'s module docstring for why).

Any caller of `ingest_document()` MUST branch on the return type before
deciding whether to run Phase 3 extraction. For example:

    from app.ingestion.base import ingest_document
    from app.ingestion.catalog import CatalogIngestResult

    result = ingest_document(path)
    if isinstance(result, CatalogIngestResult):
        records = result.records  # already ProductRecord, no LLM call
    else:
        records = [extract_product(result)]  # IngestedDocument -> Phase 3
"""

from __future__ import annotations

import os
from typing import Union

from app.ingestion.catalog import CatalogIngestResult, ingest_catalog
from app.ingestion.docx_parser import parse_docx
from app.ingestion.models import IngestedDocument
from app.ingestion.pdf_parser import parse_pdf


class UnsupportedFormatError(ValueError):
    """Raised when `ingest_document` is given a file type Phase 1 doesn't handle yet."""


_PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".csv": ingest_catalog,
    ".xlsx": ingest_catalog,
    ".xlsm": ingest_catalog,
}


def ingest_document(path: str) -> Union[IngestedDocument, CatalogIngestResult]:
    """Parse any supported document/catalog file.

    Dispatches purely on file extension (lowercased). Add a new format by
    registering it in `_PARSERS` above.

    Returns an `IngestedDocument` for PDF/DOCX (unstructured — still needs
    Phase 3 extraction), or a `CatalogIngestResult` for CSV/XLSX/XLSM
    (already-structured `ProductRecord`s — Phase 3 is skipped). Callers must
    check `isinstance(result, CatalogIngestResult)` before deciding whether
    to run extraction. See module docstring above.
    """
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        supported = ", ".join(sorted(_PARSERS))
        raise UnsupportedFormatError(
            f"Unsupported file type '{ext or '(none)'}' for '{path}'. "
            f"Supported: {supported}"
        )
    return parser(path)