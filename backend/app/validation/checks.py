"""Runs a `Specification` through its attribute dictionary rule check.

This is the piece that's been missing since Phase 0: `ATTRIBUTE_DICTIONARY`
defines NUMERIC_RANGE/PATTERN/ENUM checks per attribute, but nothing called
`resolve_attribute()` + dispatched on `CheckType` until now.
"""

from __future__ import annotations

import re
from enum import Enum

from app.schemas.attributes import AttributeSpec, CheckType, resolve_attribute
from app.schemas.product import Specification
from app.validation.units import convert_to_base

# Matches a leading number (int/float, optional sign) followed by an optional
# unit suffix, e.g. "12V", "500 mA", "-40°C" — used when `Specification.value`
# wasn't cleanly numeric on its own (unit folded into the value string rather
# than living in `Specification.unit`).
_VALUE_WITH_UNIT_SUFFIX = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([^\d\s].*)?\s*$")


class CheckOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNVERIFIABLE = "unverifiable"  # unknown attribute, or value/unit couldn't be parsed


def _parse_numeric(value: str, declared_unit: str | None) -> tuple[float, str | None] | None:
    """Extracts (number, unit) from a spec's value/unit pair.

    Prefers `declared_unit`; falls back to a unit suffix embedded in `value`
    itself (e.g. "12V" with no separate unit field). Returns None if no
    number could be parsed at all.
    """
    try:
        return float(value.strip()), declared_unit
    except ValueError:
        pass

    match = _VALUE_WITH_UNIT_SUFFIX.match(value)
    if not match:
        return None
    number = float(match.group(1))
    suffix = (match.group(2) or "").strip() or declared_unit
    return number, suffix


def _check_numeric_range(spec: Specification, attr: AttributeSpec) -> tuple[CheckOutcome, str]:
    parsed = _parse_numeric(spec.value, spec.unit)
    if parsed is None:
        return CheckOutcome.UNVERIFIABLE, f"could not parse '{spec.value}' as a number"
    number, unit = parsed

    if unit:
        converted = convert_to_base(number, unit)
        if converted is None:
            return CheckOutcome.UNVERIFIABLE, f"unrecognized unit '{unit}' for {attr.attribute}"
        number, _ = converted
    # No unit at all: assume the bare number is already in the attribute's base unit.

    if attr.min_value is not None:
        below_min = number <= attr.min_value if attr.min_exclusive else number < attr.min_value
        if below_min:
            return CheckOutcome.FAIL, f"{number} is below minimum {attr.min_value} {attr.unit_hint or ''}".strip()
    if attr.max_value is not None and number > attr.max_value:
        return CheckOutcome.FAIL, f"{number} is above maximum {attr.max_value} {attr.unit_hint or ''}".strip()
    return CheckOutcome.PASS, f"{number} within [{attr.min_value}, {attr.max_value}]"


def _check_pattern(spec: Specification, attr: AttributeSpec) -> tuple[CheckOutcome, str]:
    if not attr.pattern:
        return CheckOutcome.UNVERIFIABLE, f"no pattern defined for {attr.attribute}"
    value = spec.value.strip()
    if attr.attribute == "thread_size":
        value = re.sub(r"\s*[×x]\s*", "x", value, flags=re.IGNORECASE)
    if re.match(attr.pattern, value):
        return CheckOutcome.PASS, f"'{spec.value}' matches expected format"
    return CheckOutcome.FAIL, f"'{spec.value}' does not match expected format for {attr.attribute}"


def _check_enum(spec: Specification, attr: AttributeSpec) -> tuple[CheckOutcome, str]:
    if not attr.enum_values:
        return CheckOutcome.UNVERIFIABLE, f"no enum values defined for {attr.attribute}"
    normalized = spec.value.strip().lower()
    if normalized in {v.lower() for v in attr.enum_values}:
        return CheckOutcome.PASS, f"'{spec.value}' is a known {attr.attribute} value"
    return CheckOutcome.FAIL, f"'{spec.value}' is not a recognized {attr.attribute} value"


def run_attribute_check(spec: Specification) -> tuple[CheckOutcome, str]:
    """Validates `spec.value` against its attribute dictionary entry.

    Returns UNVERIFIABLE (not FAIL) when the attribute isn't in the
    dictionary at all, or when the value/unit can't be parsed — an unknown
    or malformed-but-plausible attribute stays valid, just lower-confidence
    downstream, matching the contract `attributes.py` already documents for
    unresolved attribute names.
    """
    attr = resolve_attribute(spec.attribute)
    if attr is None:
        return CheckOutcome.UNVERIFIABLE, f"'{spec.attribute}' is not in the attribute dictionary"

    if attr.check == CheckType.NUMERIC_RANGE:
        return _check_numeric_range(spec, attr)
    if attr.check == CheckType.PATTERN:
        return _check_pattern(spec, attr)
    if attr.check == CheckType.ENUM:
        return _check_enum(spec, attr)
    return CheckOutcome.UNVERIFIABLE, f"unhandled check type for {attr.attribute}"
