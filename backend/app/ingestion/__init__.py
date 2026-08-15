from app.ingestion.base import UnsupportedFormatError, ingest_document
from app.ingestion.catalog import CatalogIngestResult, ColumnMappingStats, ingest_catalog
from app.ingestion.catalog_crawler import CatalogResult, discover_product_links, ingest_catalog_url
from app.ingestion.docx_parser import parse_docx
from app.ingestion.models import BlockType, ContentBlock, IngestedDocument, SourceFormat
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.url_ingest import ingest_url
from app.ingestion.web_fetcher import FetchError
from app.ingestion.web_parser import parse_html

__all__ = [
    "ingest_document",
    "UnsupportedFormatError",
    "parse_pdf",
    "parse_docx",
    "IngestedDocument",
    "ContentBlock",
    "BlockType",
    "SourceFormat",
    "ingest_catalog",
    "CatalogIngestResult",
    "ColumnMappingStats",
    "ingest_url",
    "parse_html",
    "FetchError",
    "discover_product_links",
    "ingest_catalog_url",
    "CatalogResult",
]
