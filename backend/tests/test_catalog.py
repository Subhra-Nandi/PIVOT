"""Phase 2 tests for CSV/XLSX catalog ingestion.

Fixtures build tiny CSV/XLSX files on the fly (via csv/openpyxl) rather than
committing binary sample files — same rationale as test_ingestion.py.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import csv

import pytest
from openpyxl import Workbook

from app.ingestion.catalog import CatalogIngestResult, ingest_catalog
from app.schemas.product import SpecStatus


@pytest.fixture()
def sample_csv_path(tmp_path):
    path = tmp_path / "catalog.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Product Name", "Brand", "SKU", "Rated Voltage", "Weird Column", "Price"]
        )
        writer.writerow(["ACS37800 Power Meter", "SparkFun", "SPX-001", "12V", "??", "24.95"])
        writer.writerow(["M8 Hex Bolt", "Bolt Depot", "BD-054", "", "n/a", "0.50"])
    return str(path)


@pytest.fixture()
def missing_name_csv_path(tmp_path):
    path = tmp_path / "missing_name.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Product Name", "SKU"])
        writer.writerow(["", "SKU-999"])  # falls back to SKU
        writer.writerow(["", ""])  # no name, no fallback -> skipped
    return str(path)


@pytest.fixture()
def sample_xlsx_path(tmp_path):
    path = tmp_path / "catalog.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Product Name", "Brand", "Current Rating"])
    ws.append(["Relay Module", "Adafruit", 2.5])
    wb.save(str(path))
    return str(path)


def test_ingest_csv_returns_result(sample_csv_path):
    result = ingest_catalog(sample_csv_path)
    assert isinstance(result, CatalogIngestResult)
    assert result.source_format == "csv"
    assert result.total_rows == 2
    assert len(result.records) == 2


def test_ingest_csv_maps_core_fields(sample_csv_path):
    result = ingest_catalog(sample_csv_path)
    record = result.records[0]
    assert record.product_name == "ACS37800 Power Meter"
    assert record.brand == "SparkFun"
    assert record.identifiers.sku == "SPX-001"
    assert record.commercial.price.value == 24.95


def test_ingest_csv_maps_spec_via_resolve_attribute(sample_csv_path):
    result = ingest_catalog(sample_csv_path)
    record = result.records[0]
    voltage_specs = [s for s in record.specifications if s.attribute == "voltage_rating"]
    assert len(voltage_specs) == 1
    spec = voltage_specs[0]
    assert spec.value == "12V"
    assert spec.status == SpecStatus.EXTRACTED
    assert spec.source.reference == "src-1"
    assert "row 1" in spec.source.snippet
    assert "Rated Voltage" in spec.source.snippet


def test_ingest_csv_empty_cell_not_emitted_as_spec(sample_csv_path):
    result = ingest_catalog(sample_csv_path)
    bolt_record = result.records[1]
    # Rated Voltage was blank for the bolt row -> no spec, not an empty-string spec.
    assert all(s.attribute != "voltage_rating" for s in bolt_record.specifications)


def test_ingest_csv_unknown_column_reported_and_preserved(sample_csv_path):
    result = ingest_catalog(sample_csv_path)
    assert "Weird Column" in result.column_stats.unmapped
    spec = next(s for s in result.records[0].specifications if s.attribute == "weird_column")
    assert spec.value == "??"
    assert spec.status == SpecStatus.NEEDS_REVIEW


def test_ingest_csv_column_stats_counts(sample_csv_path):
    result = ingest_catalog(sample_csv_path)
    assert result.column_stats.total_columns == 6
    assert "product_name" in result.column_stats.mapped_core
    assert "brand" in result.column_stats.mapped_core
    assert result.column_stats.mapped_spec.get("Rated Voltage") == "voltage_rating"


def test_ingest_csv_name_falls_back_to_sku(missing_name_csv_path):
    result = ingest_catalog(missing_name_csv_path)
    assert result.total_rows == 1
    assert len(result.records) == 1
    assert result.records[0].product_name == "SKU-999"


def test_ingest_xlsx_returns_result(sample_xlsx_path):
    result = ingest_catalog(sample_xlsx_path)
    assert result.source_format == "xlsx"
    assert len(result.records) == 1
    record = result.records[0]
    assert record.product_name == "Relay Module"
    assert record.brand == "Adafruit"
    current_specs = [s for s in record.specifications if s.attribute == "current_rating"]
    assert len(current_specs) == 1
    assert current_specs[0].value == "2.5"


def test_ingest_catalog_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ingest_catalog("/tmp/does-not-exist-12345.csv")


def test_ingest_catalog_unsupported_extension_raises(tmp_path):
    path = tmp_path / "catalog.txt"
    path.write_text("nope")
    with pytest.raises(ValueError):
        ingest_catalog(str(path))
