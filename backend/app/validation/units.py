"""Fixed unit-conversion table — scoped to exactly the units that appear in
`ATTRIBUTE_DICTIONARY` (app/schemas/attributes.py). Not a general unit
library: a NUMERIC_RANGE check needs to compare "500 mA" against a bound
expressed in "A", so this covers only that.

Each attribute's base unit is its `allowed_units[0]` entry — the unit its
min_value/max_value are written in.
"""

from __future__ import annotations

from typing import Optional

# unit -> (base_unit, multiplier-to-base)
_CONVERSIONS: dict[str, tuple[str, float]] = {
    # Voltage — base V
    "v": ("v", 1.0),
    "kv": ("v", 1000.0),
    "mv": ("v", 0.001),
    # Current — base A
    "a": ("a", 1.0),
    "ma": ("a", 0.001),
    # Temperature — treated as equivalent, no scaling
    "°c": ("°c", 1.0),
    "c": ("°c", 1.0),
    "degc": ("°c", 1.0),
    # Length — base mm
    "mm": ("mm", 1.0),
    "cm": ("mm", 10.0),
    "m": ("mm", 1000.0),
    "in": ("mm", 25.4),
    "ft": ("mm", 304.8),
    # Mass — base g
    "g": ("g", 1.0),
    "kg": ("g", 1000.0),
    "mg": ("g", 0.001),
    "lb": ("g", 453.59237),
    "oz": ("g", 28.349523),
    # Pressure/strength — base MPa
    "mpa": ("mpa", 1.0),
    "n/mm²": ("mpa", 1.0),  # 1 N/mm^2 == 1 MPa
    "psi": ("mpa", 0.00689476),
    "ksi": ("mpa", 6.89476),
}


def convert_to_base(value: float, unit: Optional[str]) -> Optional[tuple[float, str]]:
    """Converts `value` (given in `unit`) to its attribute's base unit.

    Returns (converted_value, base_unit_key) or None if `unit` is unrecognized
    — callers treat an unrecognized unit as UNVERIFIABLE, not a failed check.
    """
    if not unit:
        return None
    entry = _CONVERSIONS.get(unit.strip().lower())
    if entry is None:
        return None
    base_unit, multiplier = entry
    return value * multiplier, base_unit


def base_unit_of(unit: Optional[str]) -> Optional[str]:
    """Returns the base-unit key for `unit`, or None if unrecognized."""
    if not unit:
        return None
    entry = _CONVERSIONS.get(unit.strip().lower())
    return entry[0] if entry else None
