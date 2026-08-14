"""Core product record schema — the single source of truth for PIVOT.

Everything downstream derives from these models:
- FastAPI validates request/response bodies against them.
- The LLM extraction layer feeds `ProductRecord.model_json_schema()` to the
  provider as the target structure (schema-guided extraction, Phase 3).
- The validation layer (Phase 4) reads/writes `Specification.confidence` and
  `Validation.conflicts`.
- The explainability layer (Phase 5) relies on `SpecSource` / `Source`.

Design notes:
- Domain-agnostic: the top-level shape is fixed; all category-specific detail
  lives in the `specifications` array, so no structural change is needed to
  support a new product vertical.
- LLM-facing fields are lenient (sensible defaults) so sparse extractions still
  validate; only `product_name` is required as the anchor.
- Unknown / missing values are `None`, never a sentinel like 0.0 (a price of
  0.0 is "free", not "unknown").
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field

# Bump when the record shape changes in a way consumers must notice.
SCHEMA_VERSION = "0.1.0"

# Reused confidence type: a probability in [0, 1].
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class SourceType(str, Enum):
    """Where a piece of data came from.

    Drives the trust story: document-sourced fields (spec sheets, catalogs)
    generally score higher confidence than website-sourced ones (Phase 4).
    """

    DOCUMENT = "document"
    WEBSITE = "website"


class SpecStatus(str, Enum):
    """Provenance label for a single extracted field (challenge-defined trio)."""

    EXTRACTED = "extracted"  # taken directly from a source
    INFERRED = "inferred"  # derived/normalized by the model
    NEEDS_REVIEW = "needs_review"  # low confidence or conflicting sources


class Category(BaseModel):
    """Predicted product classification plus how sure the model is.

    Confidence rides alongside the value so the UI can flag a low-trust
    category and Phase 6 commerce-taxonomy mapping can treat it cautiously.
    """

    predicted: str = ""
    confidence: Confidence = 0.0


class Identifiers(BaseModel):
    """Commerce identifiers used to match this product to catalogs and feeds.

    All optional (many sources list none). GTIN/MPN are the primary join keys
    for the Phase 6 Google Shopping / GS1 mapping.
    """

    sku: Optional[str] = None
    gtin: Optional[str] = None
    mpn: Optional[str] = None


class Media(BaseModel):
    """Product imagery gathered from sources; feeds the before/after demo view."""

    images: list[str] = Field(default_factory=list)


class Price(BaseModel):
    """A monetary amount. value=None means unknown, NOT free — 0.0 is free."""

    value: Optional[float] = None  # None = unknown; 0.0 = genuinely free
    currency: Optional[str] = None  # ISO 4217, e.g. "USD"


class Commercial(BaseModel):
    """Buy-side fields (price, availability) — the volatile, often-missing part
    of a record. Grouped so the whole block can be None when a source carries
    no commercial data at all."""

    price: Optional[Price] = None
    availability: Optional[str] = None


class SpecSource(BaseModel):
    """Inline pointer attached to a single specification.

    `reference` is meant to line up with a top-level `Source.id` in
    `Provenance.sources_used`, so a field can be traced back to a full source
    record while staying cheap for the LLM to emit.
    """

    type: SourceType
    reference: str  # Source.id, page number, or URL
    snippet: Optional[str] = None


class Specification(BaseModel):
    """One extracted product attribute — the domain-agnostic heart of the record.

    All category-specific detail lives here (a record just carries however many
    entries are relevant), so the surrounding schema never changes per vertical.
    Each entry carries its own confidence, status, and source because trust and
    explainability are tracked per-field, not just per-product.
    """

    attribute: str  # normalized key, e.g. "voltage_rating"
    value: str  # raw extracted value as a string, e.g. "12"
    unit: Optional[str] = None  # e.g. "V"; None for categorical/unitless
    confidence: Confidence = 0.0
    status: SpecStatus = SpecStatus.EXTRACTED
    source: Optional[SpecSource] = None


class Source(BaseModel):
    """A full source record referenced by id from specs and provenance."""

    id: str  # stable handle, e.g. "src-1"
    type: SourceType
    reference: str  # file name or URL
    page: Optional[int] = None
    retrieved_at: Optional[datetime] = None


class Provenance(BaseModel):
    """The authoritative list of sources behind a record, plus extraction time.

    Specs reference these entries by Source.id; the Phase 5 explainability layer
    resolves every citation against this list.
    """

    sources_used: list[Source] = Field(default_factory=list)
    extraction_timestamp: Optional[datetime] = None


class Conflict(BaseModel):
    """A disagreement between sources on one attribute's value.

    Surfaced rather than silently resolved, so the UI can flag it and a human
    can decide — the honest-disagreement signal that sells the trust story.
    """

    attribute: str
    values: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)  # Source.id references


class Validation(BaseModel):
    """Record-level trust summary from the Phase 4 validation layer: an overall
    confidence roll-up plus any cross-source conflicts detected."""

    overall_confidence: Confidence = 0.0
    conflicts: list[Conflict] = Field(default_factory=list)


class ProductRecord(BaseModel):
    """The complete commerce-ready product record — PIVOT's top-level output.

    Fixed shape across every domain; only `specifications` varies by category.
    This is the single source of truth: FastAPI validates against it, the LLM
    extraction layer targets its JSON Schema, and the validation/explainability
    layers populate its confidence and source fields.
    """

    schema_version: str = SCHEMA_VERSION
    product_id: Optional[str] = None  # assigned server-side if absent
    product_name: str
    brand: Optional[str] = None
    category: Category = Field(default_factory=Category)
    description: str = ""
    identifiers: Identifiers = Field(default_factory=Identifiers)
    media: Media = Field(default_factory=Media)
    commercial: Commercial = Field(default_factory=Commercial)
    compliance: list[str] = Field(default_factory=list)
    specifications: list[Specification] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    validation: Validation = Field(default_factory=Validation)
