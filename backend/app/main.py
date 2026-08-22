"""FastAPI wrapper around PIVOT's pipeline.

Every route here is a thin adapter — routing on file extension, writing an
upload to a temp path, and calling straight into the same functions the test
suite already exercises (`parse_pdf`, `parse_docx`, `ingest_url`,
`ingest_catalog`, `extract_product`, `map_to_all`). No pipeline logic lives
here; this file's only job is HTTP <-> Python plumbing, so a bug in
extraction/validation/commerce mapping is still caught by the existing 186
tests, not hidden behind a new layer.

Response shape deliberately mirrors the frontend's static demo-data files
(`{"product_record": ..., "commerce": {...}}`), so the frontend can switch
from `fetch("/demo-data/...")` to `fetch("/api/...")` later with minimal
changes on that side.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.commerce import map_to_all
from app.extraction.extractor import ExtractionError, extract_product
from app.ingestion.catalog import ingest_catalog
from app.ingestion.docx_parser import parse_docx
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.url_ingest import ingest_url
from app.llm.base import LLMError
from app.schemas.product import ProductRecord


_SOURCE_BLOCK_LIMIT = 200
_SOURCE_CHAR_LIMIT = 100_000


def _source_payload(doc):
    """Return bounded, citation-friendly source data from the parsed document."""
    blocks = []
    characters = 0
    truncated = False
    for block in doc.blocks:
        text = block.text
        if text is None and block.table is not None:
            text = "\n".join(" | ".join(cell or "" for cell in row) for row in block.table)
        text = text or ""
        if len(blocks) >= _SOURCE_BLOCK_LIMIT or characters + len(text) > _SOURCE_CHAR_LIMIT:
            truncated = True
            break
        item = {
            "block_id": block.block_id,
            "type": block.type.value,
            "text": text,
        }
        if block.page is not None:
            item["page"] = block.page
        if block.section is not None:
            item["section"] = block.section
        blocks.append(item)
        characters += len(text)
    return {
        "filename": doc.source_filename,
        "format": doc.source_format.value,
        "page_count": doc.page_count,
        "blocks": blocks,
        "truncated": truncated,
        "warnings": doc.warnings,
    }

app = FastAPI(
    title="PIVOT API",
    description="Product intelligence: ingest a document, catalog, or URL and get back a validated, cited, commerce-mapped product record.",
    version="0.1.0",
)

# Azure App Service (and most static-hosting setups for the frontend) puts
# the API on a different origin than the UI, so CORS has to be explicit.
# ALLOWED_ORIGINS is a comma-separated list set via an App Service
# Application Setting; "*" (the default) is fine for a hackathon demo but
# should be narrowed to the frontend's actual origin for anything longer-lived.
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allowed_origins == "*" else _allowed_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class UrlRequest(BaseModel):
    url: str


class CommerceRequest(BaseModel):
    record: ProductRecord


@app.get("/health")
def health():
    """Azure App Service (and any uptime check) pings this to confirm the
    container is up and actually serving, not just that the process started."""
    return {"status": "ok"}


@app.post("/extract/file")
async def extract_from_file(file: UploadFile = File(...)):
    """Accepts a PDF, DOCX, CSV, or XLSX upload and returns the extracted
    record(s) plus their commerce mapping.

    CSV/XLSX go through `ingest_catalog()` directly — no LLM call, already
    validated internally, and can return multiple rows as multiple records.
    PDF/DOCX go through `extract_product()`, which is the one LLM-backed
    path and therefore the one that can raise `ExtractionError`/`LLMError`
    if every configured provider fails or no API key is set.
    """
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in {".pdf", ".docx", ".csv", ".xlsx", ".xlsm"}:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Use .pdf, .docx, .csv, .xlsx, or .xlsm.")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        if suffix in {".csv", ".xlsx", ".xlsm"}:
            result = ingest_catalog(tmp_path)
            if not result.records:
                raise HTTPException(400, "No valid product records found in catalog file.")

            first_record = result.records[0]
            return {
                "product_record": first_record.model_dump(mode="json"),
                "commerce": map_to_all(first_record),
                "source_format": result.source_format,
                "total_rows": result.total_rows,
                "row_warnings": result.row_warnings,
                "catalog": {"sheet": result.sheet, "header_row": result.header_row, "total_rows": result.total_rows, "accepted_rows": len(result.records), "rejected_rows": result.rejected_rows},
                "column_mapping": result.column_stats.mapping_details,
                "warnings": result.warnings,
                "items": [
                    {"product_record": record.model_dump(mode="json"), "commerce": map_to_all(record)}
                    for record in result.records
                ],
            }

        doc = parse_pdf(tmp_path) if suffix == ".pdf" else parse_docx(tmp_path)
        doc.source_filename = os.path.basename(file.filename or doc.source_filename)
        try:
            record = extract_product(doc)
        except (ExtractionError, LLMError) as exc:
            raise HTTPException(502, f"Extraction failed: {exc}") from exc

        return {
            "product_record": record.model_dump(mode="json"),
            "source": _source_payload(doc),
            "commerce": map_to_all(record),
        }
    finally:
        os.unlink(tmp_path)


@app.post("/extract/url")
def extract_from_url(request: UrlRequest):
    """Fetches a single product page (static fetch, Firecrawl fallback for
    JS-heavy/bot-walled sites — see `ingestion/web_fetcher.py`) and extracts
    a record from it."""
    try:
        doc = ingest_url(request.url)
    except Exception as exc:  # noqa: BLE001 — surfaced to the caller as-is
        raise HTTPException(502, f"Could not fetch '{request.url}': {exc}") from exc

    try:
        record = extract_product(doc)
    except (ExtractionError, LLMError) as exc:
        raise HTTPException(502, f"Extraction failed: {exc}") from exc

    return {
        "product_record": record.model_dump(mode="json"),
        "commerce": map_to_all(record),
    }


@app.post("/commerce")
def commerce_for_record(request: CommerceRequest):
    """Maps an already-built `ProductRecord` onto all three commerce
    standards. Exists separately from the /extract/* routes so the frontend
    can re-run commerce mapping after a client-side conflict resolution
    without re-running extraction — pass the edited record back in."""
    return map_to_all(request.record)
