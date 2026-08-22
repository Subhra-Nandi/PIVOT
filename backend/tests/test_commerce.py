"""Phase 6 tests: commerce schema mapping (Schema.org / Google Shopping /
ETIM-style industrial classification) and each mapper's own validator.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.commerce.google_shopping import to_google_shopping, validate_google_shopping
from app.commerce.industrial import to_industrial_classification, validate_industrial_classification
from app.commerce.mapping import map_to_all
from app.commerce.normalize import (
    confidence_bucket,
    is_known_currency,
    match_availability,
    normalize_currency,
    normalized_unit_value,
)
from app.commerce.schema_org import to_schema_org, validate_schema_org
from app.schemas.product import (
    Category,
    Commercial,
    Identifiers,
    Media,
    Price,
    ProductRecord,
    Provenance,
    Source,
    SourceType,
    SpecSource,
    Specification,
    SpecStatus,
    Validation,
)


def _full_record() -> ProductRecord:
    """A well-populated record — the "happy path" for all three mappers."""
    return ProductRecord(
        product_name="M8 Connector",
        brand="Acme",
        description="Rugged M8 circular connector for industrial sensors.",
        category=Category(predicted="Electrical Connectors", confidence=0.92),
        identifiers=Identifiers(sku="ACM-M8-001", gtin="00012345678905", mpn="M8-4P-STR"),
        media=Media(images=["https://example.com/m8.jpg", "https://example.com/m8-side.jpg"]),
        commercial=Commercial(price=Price(value=12.5, currency="usd"), availability="In Stock - ships today"),
        specifications=[
            Specification(
                attribute="voltage_rating",
                value="12",
                unit="V",
                confidence=0.9,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(type=SourceType.DOCUMENT, reference="src-1", snippet="Rated Voltage: 12V"),
            ),
            Specification(
                attribute="current_rating",
                value="500",
                unit="mA",
                confidence=0.85,
                status=SpecStatus.EXTRACTED,
                source=SpecSource(type=SourceType.DOCUMENT, reference="src-1"),
            ),
            Specification(
                attribute="material",
                value="stainless steel",
                confidence=0.7,
                status=SpecStatus.INFERRED,
                source=SpecSource(type=SourceType.WEBSITE, reference="src-2"),
            ),
        ],
        provenance=Provenance(
            sources_used=[
                Source(id="src-1", type=SourceType.DOCUMENT, reference="m8_datasheet.pdf", page=2),
                Source(
                    id="src-2",
                    type=SourceType.WEBSITE,
                    reference="https://acme.example.com/products/m8-connector",
                    retrieved_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                ),
            ],
            extraction_timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        ),
        validation=Validation(overall_confidence=0.85),
    )


def _sparse_record() -> ProductRecord:
    """Only the one required field — every mapper must still produce valid,
    if minimal, output rather than raising."""
    return ProductRecord(product_name="Unknown Widget")


# --- normalize.py ---


def test_match_availability_common_phrases():
    assert match_availability("In Stock") == "in_stock"
    assert match_availability("Ships in 3 days") == "in_stock"
    assert match_availability("Out of Stock") == "out_of_stock"
    assert match_availability("Sold Out") == "out_of_stock"
    assert match_availability("Pre-order now") == "preorder"
    assert match_availability("On backorder") == "backorder"


def test_match_availability_no_match_returns_none():
    assert match_availability("Call for pricing") is None
    assert match_availability(None) is None


def test_match_availability_handles_underscore_snake_case():
    """Regression test: ingest_catalog() (and this repo's own
    demo_catalog.csv fixture) stores availability as PIVOT's internal
    snake_case convention ("in_stock"/"out_of_stock"), not the
    space-separated phrasing the keyword table was written against. Every
    catalog-sourced record must still match correctly, or the demo's own
    fixture data would show a false "availability missing" warning."""
    assert match_availability("in_stock") == "in_stock"
    assert match_availability("out_of_stock") == "out_of_stock"
    assert match_availability("IN_STOCK") == "in_stock"


def test_normalize_currency_uppercases():
    assert normalize_currency("usd") == "USD"
    assert normalize_currency(None) is None


def test_is_known_currency():
    assert is_known_currency("USD") is True
    assert is_known_currency("usd") is True
    assert is_known_currency("XYZ") is False
    assert is_known_currency(None) is False


def test_confidence_bucket_thresholds():
    assert confidence_bucket(0.95) == "high"
    assert confidence_bucket(0.8) == "high"
    assert confidence_bucket(0.79) == "medium"
    assert confidence_bucket(0.5) == "medium"
    assert confidence_bucket(0.2) == "low"


def test_normalized_unit_value_handles_unit_embedded_in_value():
    """Regression test: Phase 4's checks.py parses "12V" (unit folded into
    the value string, no separate spec.unit) via a regex fallback because
    real Gemini output takes this shape. normalize.py used to call bare
    float(spec.value) and silently return (None, None) on the exact same
    input Phase 4 handles fine — the same data rendering worse in commerce
    output purely because of how the LLM happened to phrase it."""
    embedded = Specification(
        attribute="voltage_rating", value="12V", confidence=0.9, status=SpecStatus.EXTRACTED
    )
    split = Specification(
        attribute="voltage_rating", value="12", unit="V", confidence=0.9, status=SpecStatus.EXTRACTED
    )
    assert normalized_unit_value(embedded) == normalized_unit_value(split) == (12.0, "v")


# --- schema_org.py ---


def test_to_schema_org_full_record_has_core_fields():
    doc = to_schema_org(_full_record())
    assert doc["@context"] == "https://schema.org"
    assert doc["@type"] == "Product"
    assert doc["name"] == "M8 Connector"
    assert doc["brand"] == {"@type": "Brand", "name": "Acme"}
    assert doc["sku"] == "ACM-M8-001"
    assert doc["gtin"] == "00012345678905"
    assert doc["image"] == ["https://example.com/m8.jpg", "https://example.com/m8-side.jpg"]


def test_to_schema_org_offers_has_normalized_currency_and_availability():
    doc = to_schema_org(_full_record())
    assert doc["offers"]["price"] == 12.5
    assert doc["offers"]["priceCurrency"] == "USD"
    assert doc["offers"]["availability"] == "https://schema.org/InStock"


def test_to_schema_org_additional_properties_carry_confidence_and_status():
    doc = to_schema_org(_full_record())
    voltage = next(p for p in doc["additionalProperty"] if p["name"] == "voltage_rating")
    assert voltage["value"] == 12.0
    # unitCode must be a real UN/CEFACT code or omitted, never the internal
    # base-unit key normalize.py uses ("v") — see schema_org.py's docstring.
    assert "unitCode" not in voltage
    assert voltage["unitText"] == "V"
    assert "0.90" in voltage["description"]
    assert "extracted" in voltage["description"]


def test_to_schema_org_additional_properties_never_emit_internal_unit_key_as_code():
    """Regression test: normalize.py's internal base-unit keys (lowercase,
    e.g. "v", "mm", "mpa") must never be surfaced as Schema.org's unitCode,
    which is defined as a UN/CEFACT Common Code or URL — this pipeline has
    no licensed code table to produce those."""
    doc = to_schema_org(_full_record())
    for prop in doc["additionalProperty"]:
        assert "unitCode" not in prop


def test_to_schema_org_sparse_record_is_still_minimally_valid():
    doc = to_schema_org(_sparse_record())
    assert doc["name"] == "Unknown Widget"
    assert "offers" not in doc
    assert "additionalProperty" not in doc
    issues = validate_schema_org(doc)
    assert not any(i.startswith("required:") for i in issues)


def test_validate_schema_org_full_record_has_no_required_issues():
    doc = to_schema_org(_full_record())
    issues = validate_schema_org(doc)
    assert not any(i.startswith("required:") for i in issues)


def test_validate_schema_org_flags_missing_name():
    issues = validate_schema_org({"@context": "https://schema.org", "@type": "Product"})
    assert any("name is missing" in i for i in issues)


def test_validate_schema_org_flags_price_without_currency():
    doc = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "X",
        "offers": {"@type": "Offer", "price": 10},
    }
    issues = validate_schema_org(doc)
    assert any("priceCurrency is missing" in i for i in issues)


# --- google_shopping.py ---


def test_to_google_shopping_full_record_maps_required_fields():
    item = to_google_shopping(_full_record())
    assert item["id"] == "ACM-M8-001"
    assert item["title"] == "M8 Connector"
    assert item["link"] == "https://acme.example.com/products/m8-connector"
    assert item["image_link"] == "https://example.com/m8.jpg"
    assert item["additional_image_link"] == "https://example.com/m8-side.jpg"
    assert item["price"] == "12.50 USD"
    assert item["availability"] == "in_stock"
    assert item["gtin"] == "00012345678905"
    assert item["mpn"] == "M8-4P-STR"


def test_to_google_shopping_custom_label_reflects_overall_confidence():
    item = to_google_shopping(_full_record())
    assert item["custom_label_0"] == "high"


def test_to_google_shopping_id_falls_back_to_product_name_when_no_sku():
    record = _sparse_record()
    item = to_google_shopping(record)
    assert item["id"] == "Unknown Widget"


def test_to_google_shopping_omits_price_with_unrecognized_currency():
    record = _full_record()
    record.commercial.price.currency = "ZZZ"
    item = to_google_shopping(record)
    assert "price" not in item


def test_to_google_shopping_omits_link_when_no_website_source():
    record = _full_record()
    record.provenance.sources_used = [
        s for s in record.provenance.sources_used if s.type != SourceType.WEBSITE
    ]
    item = to_google_shopping(record)
    assert "link" not in item


def test_validate_google_shopping_full_record_missing_only_condition_and_category():
    item = to_google_shopping(_full_record())
    issues = validate_google_shopping(item)
    assert not any(i.startswith("required:") for i in issues)
    assert any("condition" in i for i in issues)
    assert any("google_product_category" in i for i in issues)


def test_validate_google_shopping_sparse_record_flags_required_fields():
    item = to_google_shopping(_sparse_record())
    issues = validate_google_shopping(item)
    required_issues = [i for i in issues if i.startswith("required:")]
    assert any("link" in i for i in required_issues)
    assert any("image_link" in i for i in required_issues)
    assert any("price" in i for i in required_issues)


# --- industrial.py ---


def test_to_industrial_classification_has_no_fabricated_codes():
    doc = to_industrial_classification(_full_record())
    assert doc["class_code"] is None
    assert all(f["feature_code"] is None for f in doc["features"])
    assert "no ETIM/UNSPSC" in doc["classification_note"]


def test_to_industrial_classification_features_use_normalized_units():
    doc = to_industrial_classification(_full_record())
    voltage = next(f for f in doc["features"] if f["feature_name"] == "voltage_rating")
    current = next(f for f in doc["features"] if f["feature_name"] == "current_rating")
    assert voltage["value"] == 12.0 and voltage["unit"] == "v"
    # 500 mA -> 0.5 A
    assert current["value"] == pytest.approx(0.5) and current["unit"] == "a"


def test_to_industrial_classification_categorical_spec_keeps_raw_value():
    doc = to_industrial_classification(_full_record())
    material = next(f for f in doc["features"] if f["feature_name"] == "material")
    assert material["value"] == "stainless steel"
    assert material["unit"] is None


def test_validate_industrial_classification_flags_missing_class_name():
    doc = to_industrial_classification(_sparse_record())
    issues = validate_industrial_classification(doc)
    assert any("class_name is missing" in i for i in issues)


def test_validate_industrial_classification_flags_numeric_value_without_unit():
    doc = {
        "class_name": "Widgets",
        "features": [{"feature_name": "length", "value": 45, "unit": None}],
    }
    issues = validate_industrial_classification(doc)
    assert any("has a numeric value but no resolvable unit" in i for i in issues)


def test_validate_industrial_classification_does_not_flag_genuinely_unitless_attribute():
    """Regression test: an attribute the dictionary itself doesn't define
    with units (e.g. a count like pin_count) isn't "missing" a unit — it
    never had one. The old check flagged every unit-less numeric feature
    indiscriminately, which meant a normal, correct value like pin_count: 8
    produced permanent noise in a list whose whole value depends on being
    trustworthy."""
    doc = {
        "class_name": "Connectors",
        "features": [{"feature_name": "pin_count", "value": 8, "unit": None}],
    }
    issues = validate_industrial_classification(doc)
    assert not any("has a numeric value but no resolvable unit" in i for i in issues)


# --- mapping.py (orchestrator) ---


def test_map_to_all_returns_all_three_standards():
    result = map_to_all(_full_record())
    assert set(result) == {"schema_org", "google_shopping", "industrial"}
    for entry in result.values():
        assert "document" in entry and "issues" in entry


def test_map_to_all_sparse_record_does_not_raise():
    result = map_to_all(_sparse_record())
    assert result["schema_org"]["document"]["name"] == "Unknown Widget"
    assert result["google_shopping"]["document"]["title"] == "Unknown Widget"
    assert result["industrial"]["document"]["class_name"] is None
