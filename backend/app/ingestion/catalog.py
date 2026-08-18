"""Spreadsheet catalog ingestion — CSV/XLSX straight to `ProductRecord`.

Unlike PDF/DOCX/website ingestion, a catalog row is already structured: a
column header names an attribute and a cell holds its value. There is nothing
for an LLM to extract, so this module skips `IngestedDocument` and Phase 3
entirely and maps rows straight onto `ProductRecord` — the thing that makes
CSV batch scale to hundreds of rows with zero LLM calls.

Column mapping has two tiers:
- Core columns (product name, brand, sku/gtin/mpn, price, currency,
  availability, category, description) map onto `ProductRecord`'s top-level
  fields via `_CORE_COLUMNS` below.
- Everything else is resolved through `resolve_attribute()` (the same
  dictionary Phase 3/4 use) into a `Specification` entry. A column that
  resolves to neither is reported as unmapped rather than dropped silently.

Every mapped value carries provenance: `SpecSource(type=DOCUMENT,
reference=<Source.id>, snippet="row N, column 'X'")`, so Phase 5 can cite
"catalog.csv, row 5, column 'Voltage'" the same way it cites a PDF page.
"""

from __future__ import annotations

import csv
import os
from typing import Optional

from openpyxl import load_workbook
from pydantic import BaseModel, Field

from app.schemas.attributes import resolve_attribute
from app.schemas.product import (
    Category,
    Commercial,
    Identifiers,
    Price,
    Provenance,
    ProductRecord,
    Source,
    SourceType,
    SpecSource,
    Specification,
    SpecStatus,
)


# Header (lower-cased, spaces/underscores folded to one form) -> ProductRecord
# top-level field. Checked before `resolve_attribute()`, so a header like
# "Brand" lands on `ProductRecord.brand` rather than becoming a spec.
_CORE_COLUMNS = {
    "product_name": "product_name",
    "name": "product_name",
    "product name": "product_name",
    "title": "product_name",
    "brand": "brand",
    "manufacturer": "brand",
    "description": "description",
    "category": "category",
    "sku": "sku",
    "gtin": "gtin",
    "upc": "gtin",
    "ean": "gtin",
    "mpn": "mpn",
    "part number": "mpn",
    "part_number": "mpn",
    "price": "price",
    "currency": "currency",
    "availability": "availability",
    "stock status": "availability",
    "stock_status": "availability",
}


class ColumnMappingStats(BaseModel):
    """How the header row was understood — surfaced so a user can fix a typo'd
    column rather than silently losing data."""

    total_columns: int = 0
    mapped_core: list[str] = Field(default_factory=list)
    mapped_spec: dict[str, str] = Field(default_factory=dict)  # header -> canonical attribute
    unmapped: list[str] = Field(default_factory=list)


class CatalogIngestResult(BaseModel):
    """Output of `ingest_catalog()` — the records plus enough metadata to show
    a "500 rows, 480 mapped cleanly, 20 flagged" summary in the UI."""

    source_filename: str
    source_format: str  # "csv" | "xlsx"
    total_rows: int = 0
    records: list[ProductRecord] = Field(default_factory=list)
    column_stats: ColumnMappingStats = Field(default_factory=ColumnMappingStats)
    row_warnings: list[str] = Field(default_factory=list)  # e.g. "row 12: no product name"


def _normalize_header(header: str) -> str:
    return header.strip().lower()


def _read_csv_rows(path: str) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return headers, rows


def _read_xlsx_rows(path: str) -> tuple[list[str], list[dict[str, str]]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    row_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(row_iter)
    except StopIteration:
        return [], []
    headers = [str(h).strip() if h is not None else "" for h in header_row]
    rows = []
    for raw_row in row_iter:
        # Cells are typed by openpyxl (float/int/str/None) — stringify so
        # downstream mapping logic matches the CSV path exactly.
        row = {
            headers[i]: ("" if v is None else str(v))
            for i, v in enumerate(raw_row)
            if i < len(headers) and headers[i]
        }
        rows.append(row)
    return headers, rows


def _build_column_map(headers: list[str]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Classify each header once. Returns (header -> core field, header ->
    canonical attribute, unmapped headers) so per-row mapping is a dict lookup."""
    core_map: dict[str, str] = {}
    spec_map: dict[str, str] = {}
    unmapped: list[str] = []
    for header in headers:
        if not header:
            continue
        normalized = _normalize_header(header)
        core_field = _CORE_COLUMNS.get(normalized) or _CORE_COLUMNS.get(
            normalized.replace("_", " ")
        )
        if core_field:
            core_map[header] = core_field
            continue
        attr_spec = resolve_attribute(header)
        if attr_spec:
            spec_map[header] = attr_spec.attribute
        else:
            unmapped.append(header)
    return core_map, spec_map, unmapped


def _row_to_record(
    row: dict[str, str],
    row_number: int,
    core_map: dict[str, str],
    spec_map: dict[str, str],
    source_id: str,
    filename: str,
    row_warnings: list[str],
) -> Optional[ProductRecord]:
    core_values: dict[str, str] = {}
    for header, field in core_map.items():
        value = (row.get(header) or "").strip()
        if value:
            core_values[field] = value

    product_name = core_values.get("product_name")
    if not product_name:
        # Fall back to an identifier so a row with a name typo/gap isn't
        # dropped outright — flagged via row_warnings so it's still visible.
        product_name = core_values.get("sku") or core_values.get("mpn")
    if not product_name:
        row_warnings.append(f"row {row_number}: no product name (and no sku/mpn fallback), skipped")
        return None

    price_value: Optional[float] = None
    if "price" in core_values:
        try:
            price_value = float(core_values["price"].replace(",", "").lstrip("$"))
        except ValueError:
            row_warnings.append(
                f"row {row_number}: could not parse price '{core_values['price']}'"
            )

    specifications: list[Specification] = []
    for header, attribute in spec_map.items():
        raw_value = (row.get(header) or "").strip()
        if not raw_value:
            continue
        specifications.append(
            Specification(
                attribute=attribute,
                value=raw_value,
                status=SpecStatus.EXTRACTED,
                confidence=0.95,  # direct column mapping, not model-inferred
                source=SpecSource(
                    type=SourceType.DOCUMENT,
                    reference=source_id,
                    snippet=f"row {row_number}, column '{header}'",
                ),
            )
        )

    return ProductRecord(
        product_name=product_name,
        brand=core_values.get("brand"),
        category=Category(predicted=core_values.get("category", ""), confidence=1.0 if "category" in core_values else 0.0),
        description=core_values.get("description", ""),
        identifiers=Identifiers(
            sku=core_values.get("sku"),
            gtin=core_values.get("gtin"),
            mpn=core_values.get("mpn"),
        ),
        commercial=Commercial(
            price=Price(value=price_value, currency=core_values.get("currency")) if (price_value is not None or "currency" in core_values) else None,
            availability=core_values.get("availability"),
        ),
        specifications=specifications,
        provenance=Provenance(
            sources_used=[
                Source(id=source_id, type=SourceType.DOCUMENT, reference=filename)
            ]
        ),
    )


def ingest_catalog(path: str) -> CatalogIngestResult:
    """Parse a CSV or XLSX catalog file straight into `ProductRecord`s.

    No LLM call — every column is mapped deterministically via core-field
    matching or `resolve_attribute()`. Raises FileNotFoundError if `path`
    doesn't exist, ValueError for an unsupported extension.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such file: {path}")

    filename = os.path.basename(path)
    _, ext = os.path.splitext(path)
    ext = ext.lower()

    if ext == ".csv":
        source_format = "csv"
        headers, rows = _read_csv_rows(path)
    elif ext in (".xlsx", ".xlsm"):
        source_format = "xlsx"
        headers, rows = _read_xlsx_rows(path)
    else:
        raise ValueError(f"Unsupported catalog file type '{ext or '(none)'}' for '{path}'. Supported: .csv, .xlsx")

    core_map, spec_map, unmapped = _build_column_map(headers)
    column_stats = ColumnMappingStats(
        total_columns=len([h for h in headers if h]),
        mapped_core=sorted(set(core_map.values())),
        mapped_spec=spec_map,
        unmapped=unmapped,
    )

    # Imported here, not at module top level: app.validation's package init
    # (validation/groundedness.py) imports app.ingestion.models, which runs
    # this package's own __init__.py -> back to this module -> app.validation
    # while it's still mid-initialization. Deferring to call time breaks
    # that cycle. (Same root cause and fix as catalog_crawler.py's
    # extract_product import.)
    from app.validation import validate_record

    source_id = "src-1"
    records: list[ProductRecord] = []
    row_warnings: list[str] = []
    for i, row in enumerate(rows):
        # Row numbers are 1-indexed against the data rows (header excluded),
        # matching how a user reading the spreadsheet in a viewer would count.
        record = _row_to_record(row, i + 1, core_map, spec_map, source_id, filename, row_warnings)
        if record is not None:
            records.append(validate_record(record))

    return CatalogIngestResult(
        source_filename=filename,
        source_format=source_format,
        total_rows=len(rows),
        records=records,
        column_stats=column_stats,
        row_warnings=row_warnings,
    )