"""Maps a `ProductRecord` onto an ETIM-style industrial classification block:
a category plus a flat list of {feature, value, unit} entries in normalized
base units — the shape GS1/ETIM/UNSPSC-driven procurement catalogs expect a
product's technical features to arrive in.

Honest scope limit: real ETIM/UNSPSC codes (e.g. ETIM class EC000068,
feature EF000001) come from ETIM International's / GS1's licensed
classification databases, which this pipeline has no access to and can't
fabricate — a made-up code would be worse than none, since a downstream
procurement system would silently misfile the product. What this module
*can* do without that database: emit the feature/value/unit shape those
systems expect, in SI base units (via Phase 4's own conversion table), so
plugging in a real class/feature code lookup later is a data problem, not a
structural one. `class_code`/`feature_code` are left `None` and every
output carries `classification_note` saying so, rather than a card that
implies compliance it doesn't have.
"""

from __future__ import annotations

from typing import Any

from app.commerce.normalize import normalized_unit_value
from app.schemas.attributes import resolve_attribute
from app.schemas.product import ProductRecord

_CLASSIFICATION_NOTE = (
    "class_code/feature_code are unset: no ETIM/UNSPSC licensed "
    "classification database is available to this pipeline. Category and "
    "feature/value/unit structure are populated from PIVOT's own extraction "
    "and are ready to join against a real code table."
)


def _feature_entries(record: ProductRecord) -> list[dict[str, Any]]:
    entries = []
    for spec in record.specifications:
        attr_spec = resolve_attribute(spec.attribute)
        value, unit = normalized_unit_value(spec)
        entries.append(
            {
                "feature_code": None,
                "feature_name": attr_spec.attribute if attr_spec else spec.attribute,
                "value": value if value is not None else spec.value,
                "unit": unit,
                "confidence": spec.confidence,
                "status": spec.status.value,
            }
        )
    return entries


def to_industrial_classification(record: ProductRecord) -> dict[str, Any]:
    """Builds an ETIM-style classification block from a `ProductRecord`.

    See module docstring for why `class_code`/`feature_code` are always
    `None` here rather than guessed.
    """
    return {
        "class_code": None,
        "class_name": record.category.predicted or None,
        "class_name_confidence": record.category.confidence,
        "classification_note": _CLASSIFICATION_NOTE,
        "brand": record.brand,
        "mpn": record.identifiers.mpn,
        "features": _feature_entries(record),
    }


def validate_industrial_classification(doc: dict[str, Any]) -> list[str]:
    """Structural check only (this isn't validating against a real
    ETIM/UNSPSC dictionary, since none is available — see module docstring).
    Flags features with a value but no resolvable unit, and an unset class
    name, both of which limit how useful the block is downstream."""
    issues: list[str] = []

    if not doc.get("class_name"):
        issues.append("recommended: class_name is missing (no predicted category)")
    if doc.get("class_code") is not None:
        issues.append("warning: class_code is set but no code table was available to validate it against")

    for feature in doc.get("features", []):
        if feature.get("value") is None:
            issues.append(f"required: feature '{feature.get('feature_name')}' has no value")
        if isinstance(feature.get("value"), (int, float)) and not feature.get("unit"):
            issues.append(
                f"recommended: feature '{feature.get('feature_name')}' has a numeric value but no resolvable unit"
            )

    return issues
