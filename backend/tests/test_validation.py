"""Phase 4 tests for the validation layer: unit conversion, attribute-dictionary
rule checks, groundedness, and the validate_record confidence rollup.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import pytest

from app.ingestion.models import BlockType, ContentBlock
from app.schemas.product import ProductRecord, SourceType, Specification, SpecSource, SpecStatus
from app.validation.checks import CheckOutcome, run_attribute_check
from app.validation.groundedness import check_groundedness, find_block
from app.validation.units import base_unit_of, convert_to_base
from app.validation.validator import validate_record


# --- units.py ---


def test_convert_to_base_handles_si_prefixes():
    assert convert_to_base(1, "kV") == (1000.0, "v")
    assert convert_to_base(500, "mA") == (0.5, "a")


def test_convert_to_base_handles_imperial():
    value, base = convert_to_base(1, "in")
    assert base == "mm"
    assert round(value, 2) == 25.4


def test_convert_to_base_unrecognized_unit_returns_none():
    assert convert_to_base(1, "furlongs") is None
    assert convert_to_base(1, None) is None


def test_base_unit_of():
    assert base_unit_of("V") == "v"
    assert base_unit_of("psi") == "mpa"
    assert base_unit_of("bogus") is None


# --- checks.py ---


def _spec(attribute, value, unit=None, status=SpecStatus.EXTRACTED) -> Specification:
    return Specification(attribute=attribute, value=value, unit=unit, status=status)


def test_numeric_range_check_passes_within_bounds():
    outcome, _ = run_attribute_check(_spec("voltage_rating", "12", "V"))
    assert outcome == CheckOutcome.PASS


def test_numeric_range_check_fails_out_of_bounds():
    outcome, reason = run_attribute_check(_spec("voltage_rating", "5000", "V"))
    assert outcome == CheckOutcome.FAIL
    assert "above maximum" in reason


def test_numeric_range_check_parses_unit_embedded_in_value():
    outcome, _ = run_attribute_check(_spec("voltage_rating", "12V"))
    assert outcome == CheckOutcome.PASS


def test_numeric_range_check_converts_units_before_comparing():
    # 50 mA = 0.05 A, below current_rating's 0.1 A minimum once converted
    # correctly -> must FAIL, not be silently compared as if "50" were amps.
    outcome, reason = run_attribute_check(_spec("current_rating", "50", "mA"))
    assert outcome == CheckOutcome.FAIL
    assert "below minimum" in reason


def test_numeric_range_check_unparseable_value_is_unverifiable():
    outcome, _ = run_attribute_check(_spec("voltage_rating", "roughly a lot"))
    assert outcome == CheckOutcome.UNVERIFIABLE


def test_pattern_check_passes():
    outcome, _ = run_attribute_check(_spec("thread_size", "M12x1.5"))
    assert outcome == CheckOutcome.PASS


def test_pattern_check_fails():
    outcome, _ = run_attribute_check(_spec("thread_size", "not-a-thread"))
    assert outcome == CheckOutcome.FAIL


def test_enum_check_passes_case_insensitively():
    outcome, _ = run_attribute_check(_spec("material", "Stainless Steel"))
    assert outcome == CheckOutcome.PASS


def test_enum_check_fails_for_unknown_value():
    outcome, _ = run_attribute_check(_spec("material", "unobtainium"))
    assert outcome == CheckOutcome.FAIL


def test_numeric_range_check_exclusive_minimum_rejects_zero():
    # length/weight document "must be > 0" — min_value=0 with min_exclusive=True,
    # so exactly 0 must FAIL, not pass as if 0 were a valid boundary value.
    outcome, reason = run_attribute_check(_spec("length", "0", "mm"))
    assert outcome == CheckOutcome.FAIL
    assert "below minimum" in reason


def test_numeric_range_check_exclusive_minimum_allows_small_positive():
    outcome, _ = run_attribute_check(_spec("length", "0.1", "mm"))
    assert outcome == CheckOutcome.PASS


def test_unknown_attribute_is_unverifiable():
    outcome, reason = run_attribute_check(_spec("quantum_flux_capacity", "42"))
    assert outcome == CheckOutcome.UNVERIFIABLE


@pytest.mark.parametrize("value", ["M18x1", "M18 x 1", "M18×1"])
def test_thread_size_spacing_and_multiplication_sign_are_valid(value):
    outcome, _ = run_attribute_check(_spec("thread_size", value))
    assert outcome == CheckOutcome.PASS


def test_malformed_thread_size_remains_invalid():
    outcome, _ = run_attribute_check(_spec("thread_size", "M18 junk"))
    assert outcome == CheckOutcome.FAIL


# --- groundedness.py ---


def test_check_groundedness_true_for_present_value():
    block = ContentBlock(block_id="b1", type=BlockType.TEXT, text="Rated Voltage: 12V")
    assert check_groundedness("12", block) is True


def test_check_groundedness_false_for_absent_value():
    block = ContentBlock(block_id="b1", type=BlockType.TEXT, text="Rated Voltage: 12V")
    assert check_groundedness("9999", block) is False


def test_check_groundedness_checks_table_cells():
    block = ContentBlock(
        block_id="b2",
        type=BlockType.TABLE,
        table=[["Attribute", "Value"], ["Voltage", "24V"]],
    )
    assert check_groundedness("24V", block) is True
    assert check_groundedness("99V", block) is False


def test_find_block_by_id():
    blocks = [
        ContentBlock(block_id="b1", type=BlockType.TEXT, text="a"),
        ContentBlock(block_id="b2", type=BlockType.TEXT, text="b"),
    ]
    assert find_block(blocks, "b2").text == "b"
    assert find_block(blocks, "missing") is None


# --- validator.py ---


def _record_with_spec(spec: Specification) -> ProductRecord:
    return ProductRecord(product_name="Widget", specifications=[spec])


def test_validate_record_boosts_confidence_on_passing_check():
    record = _record_with_spec(_spec("voltage_rating", "12", "V"))
    validate_record(record)
    assert record.specifications[0].confidence > 0.85  # base EXTRACTED*DOCUMENT-trust + boost
    assert record.specifications[0].status == SpecStatus.EXTRACTED


def test_validate_record_demotes_status_on_failing_check():
    record = _record_with_spec(_spec("voltage_rating", "99999", "V"))
    validate_record(record)
    assert record.specifications[0].status == SpecStatus.NEEDS_REVIEW
    assert record.specifications[0].confidence < 0.5


def test_validate_record_unknown_attribute_is_unverified_with_lower_confidence():
    baseline = _record_with_spec(_spec("voltage_rating", "12", "V"))
    validate_record(baseline)

    unknown = _record_with_spec(_spec("quantum_flux_capacity", "42"))
    validate_record(unknown)

    assert unknown.specifications[0].status == SpecStatus.NEEDS_REVIEW
    assert unknown.specifications[0].confidence < baseline.specifications[0].confidence


def test_validate_record_website_source_scores_lower_than_document():
    doc_spec = _spec("voltage_rating", "12", "V")
    doc_spec.source = SpecSource(type=SourceType.DOCUMENT, reference="b1")
    doc_record = _record_with_spec(doc_spec)
    validate_record(doc_record)

    web_spec = _spec("voltage_rating", "12", "V")
    web_spec.source = SpecSource(type=SourceType.WEBSITE, reference="b1")
    web_record = _record_with_spec(web_spec)
    validate_record(web_record)

    assert web_record.specifications[0].confidence < doc_record.specifications[0].confidence


def test_validate_record_ungrounded_value_demoted_when_blocks_given():
    spec = _spec("voltage_rating", "12", "V")
    spec.source = SpecSource(type=SourceType.WEBSITE, reference="b1")
    record = _record_with_spec(spec)
    blocks = [ContentBlock(block_id="b1", type=BlockType.TEXT, text="Totally unrelated content.")]

    validate_record(record, blocks=blocks)

    assert record.specifications[0].status == SpecStatus.NEEDS_REVIEW


def test_check_groundedness_boolean_flag_is_trivially_grounded():
    # A "Yes"/"No" value is the LLM's judgment about a feature's presence,
    # synthesized from descriptive prose — the word "yes" itself need not
    # appear anywhere in the source for the flag to be correct.
    block = ContentBlock(
        block_id="b1", type=BlockType.TEXT, text="Level shifting on the UART and reset pin."
    )
    assert check_groundedness("Yes", block) is True
    assert check_groundedness("No", block) is True


def test_validate_record_grounded_value_not_penalized():
    spec = _spec("voltage_rating", "12", "V")
    spec.source = SpecSource(type=SourceType.WEBSITE, reference="b1")
    record = _record_with_spec(spec)
    blocks = [ContentBlock(block_id="b1", type=BlockType.TEXT, text="Rated Voltage: 12V")]

    validate_record(record, blocks=blocks)

    assert record.specifications[0].status == SpecStatus.EXTRACTED


def test_validate_record_rolls_up_overall_confidence():
    record = ProductRecord(
        product_name="Widget",
        specifications=[
            _spec("voltage_rating", "12", "V"),
            _spec("current_rating", "5", "A"),
        ],
    )
    validate_record(record)
    expected = round(
        sum(s.confidence for s in record.specifications) / len(record.specifications), 2
    )
    assert record.validation.overall_confidence == expected


def test_validate_record_no_specs_leaves_overall_confidence_default():
    record = ProductRecord(product_name="Widget", specifications=[])
    validate_record(record)
    assert record.validation.overall_confidence == 0.0
