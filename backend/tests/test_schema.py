"""Phase 0 smoke tests — guard the schema contract through later phases.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from app.schemas import (
    ATTRIBUTE_DICTIONARY,
    Price,
    ProductRecord,
    SpecStatus,
    resolve_attribute,
)


def test_minimal_record_validates():
    # product_name is the only required anchor; everything else defaults.
    rec = ProductRecord(product_name="M8 Hex Bolt")
    assert rec.schema_version
    assert rec.specifications == []
    assert rec.commercial is None or rec.commercial.price is None


def test_price_none_is_unknown_not_zero():
    # Unknown price must be None; 0.0 would mean "genuinely free".
    p = Price()
    assert p.value is None
    assert Price(value=0.0).value == 0.0


def test_json_schema_emits_for_llm():
    # Phase 3 feeds this to the provider as the extraction target.
    schema = ProductRecord.model_json_schema()
    assert schema["type"] == "object"
    assert "product_name" in schema["required"]
    assert "specifications" in schema["properties"]


def test_spec_status_trio():
    assert {s.value for s in SpecStatus} == {"extracted", "inferred", "needs_review"}


def test_resolve_attribute_by_alias_and_normalization():
    assert resolve_attribute("Rated Voltage").attribute == "voltage_rating"
    assert resolve_attribute("voltage_rating").attribute == "voltage_rating"
    # space <-> underscore tolerance
    assert resolve_attribute("thread size").attribute == "thread_size"
    assert resolve_attribute("operating_temperature").attribute == "operating_temp"


def test_resolve_unknown_attribute_returns_none():
    # Unknown attributes are valid-but-low-confidence downstream, not errors.
    assert resolve_attribute("flux_capacitance") is None
    assert resolve_attribute("") is None


def test_dictionary_covers_starter_set():
    expected = {
        "voltage_rating",
        "current_rating",
        "ip_rating",
        "operating_temp",
        "thread_size",
        "tensile_strength",
        "material",
        "coating",
        "length",
        "weight",
    }
    assert expected <= set(ATTRIBUTE_DICTIONARY)
