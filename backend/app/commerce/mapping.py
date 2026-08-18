"""Phase 6 entry point: run a `ProductRecord` through all three commerce
schema mappings at once and report how compliant each output is.

This is what Phase 7's demo UI calls for its "schema output view" — one
function, one dict with all three standards plus their validation issues,
so the UI doesn't need to know about `schema_org`/`google_shopping`/
`industrial` as separate modules.
"""

from __future__ import annotations

from typing import Any

from app.commerce.google_shopping import to_google_shopping, validate_google_shopping
from app.commerce.industrial import to_industrial_classification, validate_industrial_classification
from app.commerce.schema_org import to_schema_org, validate_schema_org
from app.schemas.product import ProductRecord


def map_to_all(record: ProductRecord) -> dict[str, Any]:
    """Maps `record` onto Schema.org, Google Shopping, and an ETIM-style
    industrial classification, validating each against its own standard.

    Returns:
        {
          "schema_org": {"document": {...}, "issues": [...]},
          "google_shopping": {"document": {...}, "issues": [...]},
          "industrial": {"document": {...}, "issues": [...]},
        }

    `issues` distinguishes "required:"/"recommended:"/"warning:" prefixes
    (see each mapper's own `validate_*`) so a caller — including Phase 7's
    UI — can decide how to weight them rather than treating every gap as
    equally severe.
    """
    schema_org_doc = to_schema_org(record)
    google_shopping_doc = to_google_shopping(record)
    industrial_doc = to_industrial_classification(record)

    return {
        "schema_org": {
            "document": schema_org_doc,
            "issues": validate_schema_org(schema_org_doc),
        },
        "google_shopping": {
            "document": google_shopping_doc,
            "issues": validate_google_shopping(google_shopping_doc),
        },
        "industrial": {
            "document": industrial_doc,
            "issues": validate_industrial_classification(industrial_doc),
        },
    }
