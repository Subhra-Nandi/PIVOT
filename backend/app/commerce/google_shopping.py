"""Maps a `ProductRecord` onto a Google Shopping feed item (one row of
Google's product feed spec: support.google.com/merchants/answer/7052112).

Kept as a flat dict of the feed's exact attribute names (`image_link`,
`gtin`, `google_product_category`, ...) rather than reusing PIVOT's own
field names, because the whole point of Phase 6 is producing something a
real commerce system ingests as-is — a caller should be able to
`csv.DictWriter(feed_attribute_names).writerow(to_google_shopping(record))`
without a translation step.

Every value Phase 6 can't ground in the record (a real product `link`, a
`condition`) is either omitted or explicitly marked as inferred via
`custom_label_0` rather than guessed silently onto a required-looking
field — a wrong `availability` or `condition` on a live feed gets a
listing suspended, so "omit" beats "guess" here more strongly than almost
anywhere else in the pipeline.
"""

from __future__ import annotations

from typing import Any, Optional

from app.commerce.normalize import (
    confidence_bucket,
    is_known_currency,
    match_availability,
    normalize_currency,
)
from app.schemas.product import ProductRecord, SourceType

# Google's controlled availability vocabulary (feed spec, not schema.org's —
# see schema_org.py's note on the two not sharing spellings).
_AVAILABILITY_VALUES = {"in_stock", "out_of_stock", "preorder", "backorder"}


def _feed_id(record: ProductRecord) -> str:
    """Google requires a stable, unique `id` per item. Prefer identifiers
    that already claim to be unique (product_id, then SKU); GTIN/MPN alone
    aren't guaranteed unique across a catalog the way a SKU is, so they're
    not used as the primary id even though they're included as their own
    fields."""
    return record.product_id or record.identifiers.sku or record.product_name


def _product_link(record: ProductRecord) -> Optional[str]:
    """`link` isn't a field ProductRecord carries directly — but a
    website-sourced record's own source URL *is* usually the product page,
    so it's the best available stand-in. Document-sourced-only records
    (a PDF spec sheet with no web listing) have no candidate and correctly
    get no `link`."""
    for source in record.provenance.sources_used:
        if source.type == SourceType.WEBSITE:
            return source.reference
    return None


def to_google_shopping(record: ProductRecord) -> dict[str, Any]:
    """Builds one Google Shopping feed item from a `ProductRecord`.

    Returns only the fields that could be grounded in the record — required
    fields Google itself defines (id, title) are always present since
    `product_name` is PIVOT's own only required field; everything else is
    conditional. Use `validate_google_shopping()` to check what a specific
    output is still missing before treating it as feed-ready.
    """
    item: dict[str, Any] = {
        "id": _feed_id(record),
        "title": record.product_name,
    }
    if record.description:
        item["description"] = record.description
    link = _product_link(record)
    if link:
        item["link"] = link
    if record.media.images:
        item["image_link"] = record.media.images[0]
        if len(record.media.images) > 1:
            item["additional_image_link"] = ",".join(record.media.images[1:])
    if record.brand:
        item["brand"] = record.brand
    if record.identifiers.gtin:
        item["gtin"] = record.identifiers.gtin
    if record.identifiers.mpn:
        item["mpn"] = record.identifiers.mpn

    commercial = record.commercial
    if commercial and commercial.price and commercial.price.value is not None:
        currency = normalize_currency(commercial.price.currency)
        if currency and is_known_currency(currency):
            item["price"] = f"{commercial.price.value:.2f} {currency}"
        # A currency-less or unrecognized-currency price is intentionally
        # omitted rather than emitted without a unit, since Google rejects
        # (rather than warns on) a price with no currency.
    if commercial and commercial.availability:
        availability = match_availability(commercial.availability)
        if availability:
            item["availability"] = availability

    # Google's own general-purpose segmentation field (support.google.com
    # /merchants/answer/6324473) — repurposed here to surface Phase 4's
    # overall confidence without inventing a non-standard feed column.
    item["custom_label_0"] = confidence_bucket(record.validation.overall_confidence)

    return item


def validate_google_shopping(item: dict[str, Any]) -> list[str]:
    """Checks `item` against Google's required-field list for a feed row.

    `condition` and `google_product_category` are flagged as recommended
    rather than injected with a guessed default (e.g. "new") — PIVOT's
    pipeline has no signal for either today, and a wrong default is worse
    than an honest gap on a real feed.
    """
    issues: list[str] = []

    if not item.get("id"):
        issues.append("required: id is missing")
    if not item.get("title"):
        issues.append("required: title is missing")
    if not item.get("description"):
        issues.append("required: description is missing")
    if not item.get("link"):
        issues.append("required: link is missing (no website-sourced URL available)")
    if not item.get("image_link"):
        issues.append("required: image_link is missing")
    if not item.get("availability"):
        issues.append("required: availability is missing or unrecognized")
    elif item["availability"] not in _AVAILABILITY_VALUES:
        issues.append(f"required: availability '{item['availability']}' is not a recognized value")
    if not item.get("price"):
        issues.append("required: price is missing (no price, no currency, or unrecognized currency)")
    if not item.get("brand") and not item.get("gtin") and not item.get("mpn"):
        issues.append("required: at least one of brand+mpn, or gtin, must identify the product")
    if not item.get("condition"):
        issues.append("recommended: condition is not set (PIVOT has no condition signal)")
    if not item.get("google_product_category"):
        issues.append("recommended: google_product_category is not set (no taxonomy match implemented)")

    return issues
