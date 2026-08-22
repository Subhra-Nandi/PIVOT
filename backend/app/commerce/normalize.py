"""Shared normalization helpers for Phase 6's commerce-schema mappers.

Deliberately thin: unit conversion itself already lives in
`app.validation.units` (Phase 4) — this module just adapts that table's
output into the string/format conventions each target schema expects
(Schema.org wants a bare numeric value plus a `unitCode`, Google Shopping
wants "<value> <unit>", the ETIM-style output wants SI base units). Reusing
Phase 4's conversion table means Phase 6 can't silently drift from the
bounds Phase 4 already validated against.

No import in this module reaches back into app.ingestion or
app.extraction — app.commerce only ever depends downward on app.schemas and
app.validation.units, both of which have no knowledge app.commerce exists,
so there's no risk of repeating the circular-import bug fixed in
catalog_crawler.py / catalog.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.schemas.attributes import resolve_attribute
from app.schemas.product import Specification
from app.validation.checks import _parse_numeric
from app.validation.units import base_unit_of, convert_to_base

# ISO 4217 is ~180 active codes; PIVOT's sources only ever emit a handful.
# Anything outside this set is passed through but flagged by
# `is_known_currency` rather than rejected outright — an unrecognized code
# is more likely a new source than a formatting error.
_KNOWN_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "JPY", "CNY", "CAD", "AUD", "CHF", "SGD",
}

# Google's controlled availability vocabulary. Source text ("In Stock",
# "Ships in 3 days", "Call for availability", ...) is free-form, so this is
# a best-effort keyword match, not a guarantee — callers should treat an
# unmatched string as `None` (omit the field) rather than guessing wrong,
# since a wrong availability value is worse than a missing one on a live feed.
_AVAILABILITY_KEYWORDS: list[tuple[str, str]] = [
    ("preorder", "preorder"),
    ("pre-order", "preorder"),
    ("backorder", "backorder"),
    ("back order", "backorder"),
    ("out of stock", "out_of_stock"),
    ("unavailable", "out_of_stock"),
    ("sold out", "out_of_stock"),
    ("discontinued", "out_of_stock"),
    ("in stock", "in_stock"),
    ("available", "in_stock"),
    ("ships", "in_stock"),
]


def normalized_unit_value(spec: Specification) -> tuple[Optional[float], Optional[str]]:
    """Parses `spec.value` and converts it (with `spec.unit`) to its
    attribute's base unit via Phase 4's conversion table.

    Reuses Phase 4's own `_parse_numeric` (checks.py) rather than
    duplicating its embedded-unit-suffix regex here. Real Gemini output
    sometimes folds the unit into the value string itself (`"12V"` with
    `unit=None`) rather than keeping them separate — `checks.py` grew a
    fallback for exactly that shape because it showed up in practice. This
    module used to parse with a bare `float(spec.value)` and silently
    return `(None, None)` on that same input: not a crash, but the same
    data rendering worse in Schema.org/ETIM output purely because of how
    the LLM happened to phrase a value that Phase 4 parses just fine.

    Returns (None, None) when the value isn't numeric, the unit is
    unrecognized, or the attribute has no dictionary entry — categorical
    specs (material, coating) and unresolvable ones fall through unchanged
    so callers can still emit the raw string elsewhere.
    """
    parsed = _parse_numeric(spec.value, spec.unit)
    if parsed is None:
        return None, None
    raw_value, unit = parsed

    if unit:
        converted = convert_to_base(raw_value, unit)
        if converted is not None:
            return converted
        return None, None

    attr_spec = resolve_attribute(spec.attribute)
    if attr_spec and attr_spec.allowed_units:
        return raw_value, base_unit_of(attr_spec.allowed_units[0])

    return raw_value, None


def is_known_currency(code: Optional[str]) -> bool:
    return bool(code) and code.strip().upper() in _KNOWN_CURRENCIES


def normalize_currency(code: Optional[str]) -> Optional[str]:
    """Upper-cases a currency code for ISO 4217 comparison. Doesn't guess a
    default — an unstated currency is unknown, not USD."""
    return code.strip().upper() if code else None


def to_iso8601(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def match_availability(raw: Optional[str]) -> Optional[str]:
    """Best-effort match of free-form availability text to Google's
    controlled vocabulary (in_stock / out_of_stock / preorder / backorder).
    Returns None on no confident match rather than defaulting to in_stock —
    an absent field is safer on a live feed than a fabricated one.

    Underscores are folded to spaces before matching: `ingest_catalog()`
    (and this repo's own demo_catalog.csv fixture) uses PIVOT's internal
    snake_case convention ("in_stock", not "in stock") for this exact
    field, so without this normalization every catalog-sourced record in
    the demo data would fail this match and show a false "availability
    missing" warning despite the value being present and valid.
    """
    if not raw:
        return None
    lowered = raw.strip().lower().replace("_", " ")
    for keyword, value in _AVAILABILITY_KEYWORDS:
        if keyword in lowered:
            return value
    return None

def confidence_bucket(score: float) -> str:
    """Coarse confidence bucket for fields (like Google's custom_label_N)
    that take a short categorical string, not a float."""
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"
