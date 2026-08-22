"""Attribute dictionary - the validation reference for extracted specs.

This is a *starter* lookup table, not an exhaustive ceiling. The Phase 4
validator dispatches generically on `check`:
- NUMERIC_RANGE: parse the value as a number, confirm it falls in [min, max].
- PATTERN: match the value against a regex (formats like IP ratings).
- ENUM: confirm the value is one of a known set (categorical attributes).

Attributes not found here are still allowed downstream — they just get a lower
default confidence rather than breaking the pipeline. `resolve_attribute`
matches on the canonical name or any alias, case-insensitively, so the LLM can
emit "Rated Voltage" and still resolve to `voltage_rating`.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CheckType(str, Enum):
    """How the Phase 4 validator should verify an attribute's value.

    Kept as data (not per-field code) so the validator dispatches generically:
    add a new attribute to the dictionary and it validates without touching the
    validator itself.
    """

    NUMERIC_RANGE = "numeric_range"
    PATTERN = "pattern"
    ENUM = "enum"


class AttributeSpec(BaseModel):
    """One row of the attribute dictionary — the validation contract for a spec.

    Holds everything the validator needs for a known attribute: which check to
    run, the expected units, the bounds/pattern/enum for that check, and the
    aliases an LLM might emit instead of the canonical name. Attributes with no
    row here still pass through — they just get lower default confidence.
    """

    attribute: str
    category: str  # "Electrical" | "Fasteners" | "Both"
    check: CheckType
    unit_hint: Optional[str] = None  # human label, e.g. "mm or in"
    allowed_units: list[str] = Field(default_factory=list)
    min_value: Optional[float] = None  # NUMERIC_RANGE
    max_value: Optional[float] = None  # NUMERIC_RANGE
    min_exclusive: bool = False  # NUMERIC_RANGE — True means value must be > min_value, not >=
    pattern: Optional[str] = None  # PATTERN (regex)
    enum_values: list[str] = Field(default_factory=list)  # ENUM
    aliases: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


_ATTRIBUTES: list[AttributeSpec] = [
    AttributeSpec(
        attribute="voltage_rating",
        category="Electrical",
        check=CheckType.NUMERIC_RANGE,
        unit_hint="V",
        allowed_units=["V", "kV", "mV"],
        min_value=1,
        max_value=1000,
        aliases=["voltage", "rated voltage", "rated volts", "rated_voltage", "voltage rating"],
        notes="Common on connectors, relays.",
    ),
    AttributeSpec(
        attribute="current_rating",
        category="Electrical",
        check=CheckType.NUMERIC_RANGE,
        unit_hint="A",
        allowed_units=["A", "mA"],
        min_value=0.1,
        max_value=100,
        aliases=["current", "rated current", "rated_current", "amperage"],
    ),
    AttributeSpec(
        attribute="ip_rating",
        category="Electrical",
        check=CheckType.PATTERN,
        pattern=r"^IP[0-6][0-9K]$",
        aliases=["ingress protection", "ip", "protection rating"],
        notes="Format check (IP00–IP69), not a numeric range.",
    ),
    AttributeSpec(
        attribute="operating_temp",
        category="Electrical",
        check=CheckType.NUMERIC_RANGE,
        unit_hint="°C",
        allowed_units=["°C", "C", "degC"],
        min_value=-40,
        max_value=150,
        aliases=[
            "operating temperature",
            "operating_temperature",
            "temperature range",
            "temp range",
        ],
        notes="Often a range, not a single value — validator may see either bound.",
    ),
    AttributeSpec(
        attribute="thread_size",
        category="Fasteners",
        check=CheckType.PATTERN,
        unit_hint="mm or in",
        # Metric (M2, M12x1.5) or imperial (#0, 1/4in, 0.25in, 2in).
        pattern=r"^(M\d+(\.\d+)?(x\d+(\.\d+)?)?|#\d+|\d+(\.\d+)?/\d+in|\d+(\.\d+)?in)$",
        aliases=["thread", "thread size", "thread diameter", "size"],
        notes="Checked against common metric/imperial thread formats.",
    ),
    AttributeSpec(
        attribute="tensile_strength",
        category="Fasteners",
        check=CheckType.NUMERIC_RANGE,
        unit_hint="MPa or psi",
        allowed_units=["MPa", "psi", "ksi", "N/mm²"],
        min_value=200,
        max_value=2000,
        aliases=["tensile", "tensile strength", "ultimate tensile strength", "uts"],
        notes="Range is grade-dependent; bounds are in MPa.",
    ),
    AttributeSpec(
        attribute="material",
        category="Fasteners",
        check=CheckType.ENUM,
        enum_values=[
            "steel",
            "stainless steel",
            "carbon steel",
            "alloy steel",
            "brass",
            "aluminum",
            "titanium",
            "nylon",
            "plastic",
        ],
        aliases=["material type", "body material", "construction"],
        notes="Categorical; extend the enum as new materials appear.",
    ),
    AttributeSpec(
        attribute="coating",
        category="Fasteners",
        check=CheckType.ENUM,
        enum_values=[
            "none",
            "zinc",
            "zinc plated",
            "black oxide",
            "galvanized",
            "chrome",
            "nickel",
            "phosphate",
        ],
        aliases=["finish", "plating", "surface finish", "surface treatment"],
    ),
    AttributeSpec(
        attribute="length",
        category="Both",
        check=CheckType.NUMERIC_RANGE,
        unit_hint="mm or in",
        allowed_units=["mm", "cm", "m", "in", "ft"],
        min_value=0,
        min_exclusive=True,  # 0 itself is not a valid length
        max_value=None,
        aliases=["overall length", "len", "size length"],
        notes="Universal; always expected. Value must be > 0.",
    ),
    AttributeSpec(
        attribute="weight",
        category="Both",
        check=CheckType.NUMERIC_RANGE,
        unit_hint="g or kg",
        allowed_units=["g", "kg", "mg", "lb", "oz"],
        min_value=0,
        min_exclusive=True,  # 0 itself is not a valid weight
        max_value=None,
        aliases=["mass", "net weight", "unit weight"],
        notes="Universal; always expected. Value must be > 0.",
    ),
]

# Canonical-name lookup.
ATTRIBUTE_DICTIONARY: dict[str, AttributeSpec] = {
    spec.attribute: spec for spec in _ATTRIBUTES
}

# Alias -> canonical name, lower-cased, built once at import.
_ALIAS_INDEX: dict[str, str] = {}
for _spec in _ATTRIBUTES:
    _ALIAS_INDEX[_spec.attribute.lower()] = _spec.attribute
    for _alias in _spec.aliases:
        _ALIAS_INDEX[_alias.lower()] = _spec.attribute


def resolve_attribute(name: str) -> Optional[AttributeSpec]:
    """Resolve a raw attribute name (canonical or alias) to its spec.

    Case-insensitive; also tolerates spaces vs. underscores. Returns None when
    the attribute is unknown — callers should treat unknown attributes as valid
    but lower-confidence, not as errors.
    """

    if not name:
        return None
    key = name.strip().lower()
    canonical = _ALIAS_INDEX.get(key)
    if canonical is None:
        # Try normalizing spaces <-> underscores before giving up.
        canonical = _ALIAS_INDEX.get(key.replace(" ", "_"))
    if canonical is None:
        canonical = _ALIAS_INDEX.get(key.replace("_", " "))
    if canonical is None:
        return None
    return ATTRIBUTE_DICTIONARY[canonical]
