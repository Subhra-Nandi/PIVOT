"""Maps a `ProductRecord` onto Schema.org's `Product` type as JSON-LD.

Chosen first among Phase 6's three targets because it's the easiest to
demo — paste the output into Google's Rich Results Test and it validates
on sight — and because `additionalProperty` (a documented, generic
Schema.org extension point, not a PIVOT invention) is exactly the slot
Phase 5's per-field confidence/status/citation data needs: nothing else in
Schema.org has room for "this spec is 0.9 confidence, extracted, and cites
page 3." Losing that here would mean Phase 6 throws away Phase 4/5's work
instead of demonstrating it, which is the opposite of what the challenge
asks for.
"""

from __future__ import annotations

from typing import Any, Optional

from app.commerce.normalize import (
    is_known_currency,
    match_availability,
    normalize_currency,
    normalized_unit_value,
    to_iso8601,
)
from app.schemas.product import ProductRecord

_CONTEXT = "https://schema.org"
_TYPE = "Product"

# Schema.org's own Offer.availability enum (a subset of schema.org/ItemAvailability).
# Distinct from Google Shopping's vocabulary in google_shopping.py — the two
# standards don't share a spelling ("InStock" vs "in_stock") even though
# they mean the same thing.
_AVAILABILITY_MAP = {
    "in_stock": "https://schema.org/InStock",
    "out_of_stock": "https://schema.org/OutOfStock",
    "preorder": "https://schema.org/PreOrder",
    "backorder": "https://schema.org/BackOrder",
}


def _additional_properties(record: ProductRecord) -> list[dict[str, Any]]:
    props = []
    for spec in record.specifications:
        value, base_unit = normalized_unit_value(spec)
        entry: dict[str, Any] = {
            "@type": "PropertyValue",
            "name": spec.attribute,
            "value": value if value is not None else spec.value,
        }
        # Schema.org's unitCode expects a UN/CEFACT Common Code (e.g. "MMT",
        # "VLT") or a URL, not an arbitrary string — this pipeline has no
        # licensed code table for that (the same honest gap
        # industrial.py's ETIM class_code documents), so the internal base
        # unit key from normalize.py (e.g. "v", "mm") must never be emitted
        # as unitCode: that's spec-invalid and leaks an internal identifier
        # into standards output. unitText is the correct field for a
        # human-readable unit with no code — prefer the originally declared
        # unit (already human-readable, e.g. "V") and only fall back to the
        # resolved base unit, uppercased, when the spec didn't state one.
        display_unit = spec.unit or (base_unit.upper() if base_unit else None)
        if display_unit:
            entry["unitText"] = display_unit
        # Phase 4/5 provenance, carried through via Schema.org's own
        # extension mechanism rather than a PIVOT-only field name.
        entry["valueReference"] = {
            "@type": "PropertyValue",
            "name": "extractionStatus",
            "value": spec.status.value,
        }
        entry["description"] = f"confidence={spec.confidence:.2f}, status={spec.status.value}"
        if spec.source and spec.source.snippet:
            entry["description"] += f", source snippet: {spec.source.snippet[:120]}"
        props.append(entry)
    return props


def _offers(record: ProductRecord) -> Optional[dict[str, Any]]:
    commercial = record.commercial
    if commercial is None or (commercial.price is None and commercial.availability is None):
        return None

    offer: dict[str, Any] = {"@type": "Offer"}
    if commercial.price and commercial.price.value is not None:
        offer["price"] = commercial.price.value
        currency = normalize_currency(commercial.price.currency)
        if currency:
            offer["priceCurrency"] = currency
    availability_key = match_availability(commercial.availability)
    if availability_key:
        offer["availability"] = _AVAILABILITY_MAP[availability_key]
    return offer or None


def to_schema_org(record: ProductRecord) -> dict[str, Any]:
    """Builds a Schema.org `Product` JSON-LD document from a `ProductRecord`.

    Every field it emits is optional-safe (a sparse record still produces
    valid, if minimal, JSON-LD) except `name`, which mirrors
    `ProductRecord.product_name` being the schema's own only required field.
    """
    doc: dict[str, Any] = {
        "@context": _CONTEXT,
        "@type": _TYPE,
        "name": record.product_name,
    }
    if record.brand:
        doc["brand"] = {"@type": "Brand", "name": record.brand}
    if record.description:
        doc["description"] = record.description
    if record.identifiers.sku:
        doc["sku"] = record.identifiers.sku
    if record.identifiers.gtin:
        doc["gtin"] = record.identifiers.gtin
    if record.identifiers.mpn:
        doc["mpn"] = record.identifiers.mpn
    if record.category.predicted:
        doc["category"] = record.category.predicted
    if record.media.images:
        doc["image"] = list(record.media.images)

    offers = _offers(record)
    if offers:
        doc["offers"] = offers

    additional_properties = _additional_properties(record)
    if additional_properties:
        doc["additionalProperty"] = additional_properties

    timestamp = to_iso8601(record.provenance.extraction_timestamp)
    if timestamp:
        doc["dateModified"] = timestamp

    return doc


def validate_schema_org(doc: dict[str, Any]) -> list[str]:
    """Checks `doc` against Schema.org's own required/recommended fields for
    `Product` (per schema.org/Product and Google's Merchant Center structured
    data guidance) rather than PIVOT's internal schema — this is Phase 6
    demonstrating standards compliance, not re-checking Phase 0's work.

    Returns a list of human-readable issues; an empty list means the
    document is at least minimally valid. Issues are worded as
    "required:"/"recommended:"/"warning:" so a caller (or the Phase 7 UI)
    can decide how strictly to treat each one.
    """
    issues: list[str] = []

    if doc.get("@context") != _CONTEXT:
        issues.append(f"required: @context must be '{_CONTEXT}'")
    if doc.get("@type") != _TYPE:
        issues.append(f"required: @type must be '{_TYPE}'")
    if not doc.get("name"):
        issues.append("required: name is missing")

    if not doc.get("image"):
        issues.append("recommended: image is missing (Google Merchant Center requires it)")
    if not doc.get("offers"):
        issues.append("recommended: offers is missing (no price/availability data)")
    else:
        offer = doc["offers"]
        if "price" in offer and "priceCurrency" not in offer:
            issues.append("required: offers.priceCurrency is missing while offers.price is present")
        if "priceCurrency" in offer and not is_known_currency(offer["priceCurrency"]):
            issues.append(f"warning: offers.priceCurrency '{offer['priceCurrency']}' is not a recognized ISO 4217 code")
    if not doc.get("sku") and not doc.get("gtin") and not doc.get("mpn"):
        issues.append("recommended: at least one of sku/gtin/mpn should be present")

    for prop in doc.get("additionalProperty", []):
        if not prop.get("name") or prop.get("value") is None:
            issues.append(f"required: additionalProperty entry missing name or value: {prop}")

    return issues
