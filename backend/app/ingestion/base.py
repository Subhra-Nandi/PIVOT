"""Single entrypoint for Phase 1 ingestion — dispatches by file extension.

This is the function everything else (Phase 3 extraction, a future FastAPI
`/extract` endpoint, ad-hoc scripts) should import, rather than reaching into
`pdf_parser` or `docx_parser` directly. Keeping one dispatch point means
adding a new format (e.g. XLSX catalogs) later only touches this file plus a
new `<format>_parser.py` — nothing that already imports `ingest_document`
needs to change.
"""

from __future__ import annotations

import os

from app.ingestion.docx_parser import parse_docx
from app.ingestion.models import IngestedDocument
from app.ingestion.pdf_parser import parse_pdf


class UnsupportedFormatError(ValueError):
    """Raised when `ingest_document` is given a file type Phase 1 doesn't handle yet."""


_PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
}


def ingest_document(path: str) -> IngestedDocument:
    """Parse any supported document into the common `IngestedDocument` shape.

    Dispatches purely on file extension (lowercased). Add a new format by
    registering it in `_PARSERS` above.
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
