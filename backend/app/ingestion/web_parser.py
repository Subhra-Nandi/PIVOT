"""HTML -> IngestedDocument — Phase 2 web ingestion.

Three extraction passes, in trust order:
1. JSON-LD `Product` blocks — Schema.org structured data a site publishes for
   its own SEO. High-trust because it's the site's own machine-readable claim
   about the product, not a heuristic guess. Emitted as a TEXT block whose
   text is a flattened "key: value" rendering, so it flows into `raw_text`
   and Phase 3 sees it like any other block, citable by block_id.
2. `<table>` elements — spec sheets are usually a table; same TABLE block
   shape PDF/DOCX already use, so Phase 3 doesn't special-case web tables.
3. Heading + paragraph text — `<h1>`-`<h6>` become `section` context (mirrors
   the DOCX section-tracking pattern), `<p>`/`<li>` become TEXT blocks.

No CSS-selector provenance beyond what `section` + `block_id` already give —
matches the PDF/DOCX citation granularity (page/section, not exact byte
offset) rather than adding a new provenance shape Phase 5 would need to learn.
"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup, Tag

from app.ingestion.models import BlockType, ContentBlock, IngestedDocument, SourceFormat
from app.ingestion.utils import make_block_id, normalize_whitespace, table_to_text

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "nav", "footer", "noscript"}


def _extract_json_ld_products(soup: BeautifulSoup) -> list[dict]:
    """Find Schema.org Product blocks among any <script type=application/ld+json>.

    A page can embed multiple JSON-LD blocks (breadcrumbs, org info, product);
    a single block can also be a list. Only @type == "Product" entries are
    kept — the rest is site-chrome metadata Phase 3 has no use for.
    """
    products: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                products.append(candidate)
    return products


def _product_json_ld_to_text(product: dict) -> str:
    """Flatten a JSON-LD Product dict into "key: value" lines.

    Nested dicts (offers, seller) are flattened one level with a dotted key
    so price/currency survive without a bespoke schema-specific parser.
    """
    lines = []
    for key, value in product.items():
        if key == "@type" or key == "@context":
            continue
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                lines.append(f"{key}.{sub_key}: {sub_value}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for sub_key, sub_value in item.items():
                        lines.append(f"{key}.{sub_key}: {sub_value}")
                else:
                    lines.append(f"{key}: {item}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def parse_html(html: str, source_url: str) -> IngestedDocument:
    """Parse a raw HTML string into an `IngestedDocument`.

    Raises ValueError if the HTML can't be parsed at all (malformed beyond
    what lxml's lenient parser tolerates, or genuinely empty).
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:
        raise ValueError(f"Could not parse HTML for '{source_url}': {exc}") from exc

    blocks: list[ContentBlock] = []
    raw_text_parts: list[str] = []
    warnings: list[str] = []
    block_index = 0

    json_ld_products = _extract_json_ld_products(soup)
    for product in json_ld_products:
        text = _product_json_ld_to_text(product)
        if not text:
            continue
        blocks.append(
            ContentBlock(block_id=make_block_id(block_index), type=BlockType.TEXT, text=text, section="JSON-LD Product")
        )
        raw_text_parts.append(text)
        block_index += 1

    body = soup.body or soup
    current_section: str | None = None

    def walk(node: Tag, section: str | None) -> str | None:
        nonlocal block_index
        for child in node.find_all(recursive=False):
            if not isinstance(child, Tag) or child.name in _SKIP_TAGS:
                continue

            if child.name in _HEADING_TAGS:
                text = normalize_whitespace(child.get_text(" ", strip=True))
                if text:
                    section = text
                    blocks.append(
                        ContentBlock(block_id=make_block_id(block_index), type=BlockType.HEADING, text=text, section=section)
                    )
                    block_index += 1
                    raw_text_parts.append(text)
                continue

            if child.name == "table":
                rows = []
                for row in child.find_all("tr"):
                    cells = [normalize_whitespace(c.get_text(" ", strip=True)) or None for c in row.find_all(["td", "th"])]
                    if any(cells):
                        rows.append(cells)
                if rows:
                    blocks.append(
                        ContentBlock(block_id=make_block_id(block_index), type=BlockType.TABLE, table=rows, section=section)
                    )
                    block_index += 1
                    raw_text_parts.append(table_to_text(rows))
                continue

            if child.name in ("p", "li"):
                text = normalize_whitespace(child.get_text(" ", strip=True))
                if text:
                    blocks.append(
                        ContentBlock(block_id=make_block_id(block_index), type=BlockType.TEXT, text=text, section=section)
                    )
                    block_index += 1
                    raw_text_parts.append(text)
                continue

            # Containers (div/section/article/...) — recurse so nested
            # headings/tables/paragraphs are still found regardless of
            # nesting depth, carrying whatever section is current so far.
            section = walk(child, section)

        return section

    walk(body, current_section)

    if not blocks:
        warnings.append(f"'{source_url}': no extractable text, tables, or JSON-LD product data")
    elif not json_ld_products:
        warnings.append(
            f"'{source_url}': no JSON-LD Product data found — relying on table/text "
            "extraction only, which is a weaker signal for Phase 3"
        )

    return IngestedDocument(
        source_filename=source_url,
        source_format=SourceFormat.WEBSITE,
        source_url=source_url,
        page_count=None,
        blocks=blocks,
        raw_text="\n\n".join(raw_text_parts),
        warnings=warnings,
    )
