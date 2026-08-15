# PIVOT

**Product Intelligence & Validation for Optimized Trade**

AI-powered product intelligence for industrial commerce: turn scattered product
data (PDFs, catalogs, websites) into structured, validated, commerce-ready
product records — with every field traceable back to its source.
> Team project — Hack2Skill

## Status

**Phase 0, Phase 1, and Phase 2 complete.** The domain-agnostic product schema
and the validation attribute dictionary are in place and tested (Phase 0). The
document ingestion pipeline — PDF and DOCX parsing into a common structured
intermediate format, with page/section references preserved for later
citation — is also in place and tested (Phase 1). Phase 2 adds three more
ingestion paths: CSV/XLSX catalog batches mapped directly to product records
(no LLM), single-product URL scraping (static fetch with a Firecrawl
fallback for JS-heavy/bot-walled sites), and catalog-listing crawling that
discovers product links and enriches them page by page. The FastAPI
`/extract` endpoint, schema-guided LLM extraction, and the React demo UI
arrive in later phases — see the [Roadmap](#roadmap).

## Prerequisites

- **Python 3.12+**
- **Git**
- Node.js — only needed once the React frontend lands (Phase 7), not yet.

## Getting started (backend)

All backend work happens in `backend/`.

```
cd backend

# 1. Create an isolated environment
python -m venv .venv

# 2. Activate it
#    Windows (PowerShell):   .venv\Scripts\Activate.ps1
#    Windows (cmd):          .venv\Scripts\activate.bat
#    macOS / Linux:          source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify the setup
pytest -q
```

If you see `48 passed`, the schema layer and all three ingestion paths
(documents, catalogs, web) are working and you're ready to build.
> **PowerShell blocks `Activate.ps1`?** Run once per terminal session: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` — or skip activation and call the venv Python directly: `.venv\Scripts\python.exe -m pytest -q`

## Environment variables

The LLM extraction layer (Phase 3) uses free-tier providers behind one swappable
interface: **Gemini** (primary) → **Groq** (fallback) → **GitHub Models** (tertiary).

```
# from the repo root
cp .env.example .env        # Windows: copy .env.example .env
```

Then fill in whatever keys you have. `.env` is gitignored — never commit it.
Free keys come from:

- **Gemini** — Google AI Studio (aistudio.google.com); use Flash / Flash-Lite, not Pro
- **Groq** — console.groq.com
- **GitHub Models** — a GitHub personal access token
- **Firecrawl** — firecrawl.dev; only needed as a fallback for JS-heavy or
  bot-walled product pages and for catalog-listing crawls. Single-page static
  scraping and CSV/XLSX/PDF/DOCX ingestion work without it.

You don't need any keys to run the current schema, ingestion pipeline, and tests.

## Project structure

```
PIVOT/
├── backend/
│   ├── app/
│   │   ├── schemas/
│   │   │   ├── product.py         # ProductRecord — the single source of truth
│   │   │   └── attributes.py      # attribute dictionary used for validation
│   │   └── ingestion/
│   │       ├── models.py          # IngestedDocument / ContentBlock — intermediate format
│   │       ├── pdf_parser.py      # PDF text + table extraction (pdfplumber)
│   │       ├── docx_parser.py     # DOCX text + table extraction (python-docx)
│   │       ├── base.py            # ingest_document() — PDF/DOCX dispatch entrypoint
│   │       ├── catalog.py         # ingest_catalog() — CSV/XLSX → ProductRecord, no LLM
│   │       ├── web_fetcher.py     # fetch_html() — static fetch + Firecrawl fallback
│   │       ├── web_parser.py      # parse_html() — JSON-LD/tables/text → IngestedDocument
│   │       ├── url_ingest.py      # ingest_url() — single-product-URL entrypoint + cache
│   │       ├── catalog_crawler.py # ingest_catalog_url() — listing discovery + enrichment
│   │       └── utils.py           # shared parsing helpers
│   ├── fixtures/
│   │   ├── catalogs/              # committed demo_catalog.csv
│   │   └── web/                   # committed raw HTML for the verified demo URLs
│   ├── scripts/
│   │   └── seed_web_cache.py      # pre-warms the web cache from fixtures before a demo
│   ├── tests/                     # pytest suite guarding the schema + ingestion contracts
│   └── requirements.txt
├── .env.example                   # copy to .env, add LLM/Firecrawl keys
└── README.md
```

`schemas/product.py` is the one file everything else derives from: FastAPI
validates against it, the LLM extraction layer targets its JSON Schema, and the
validation/explainability layers populate its confidence and source fields.

`ingestion/base.py`'s `ingest_document(path)` is the entrypoint for file-based
sources — it dispatches to the right parser by file extension and returns a
normalized `IngestedDocument`, regardless of whether the source was a PDF or
a DOCX. `ingest_catalog(path)` is a separate entrypoint for CSV/XLSX: a
spreadsheet is already structured, so it maps columns straight to
`ProductRecord` with no LLM call, rather than going through
`IngestedDocument`. `ingest_url(url)` and `ingest_catalog_url(url)` cover the
two web paths — a single product page, or a listing page whose product links
get discovered once and enriched page by page.

> **Known gap — web ingestion produces `IngestedDocument`, not `ProductRecord`
> yet.** `ingest_catalog_url()`'s `CatalogResult.enriched` is currently
> `list[IngestedDocument]`. Turning a scraped page into a `ProductRecord`
> needs schema-guided LLM extraction, which is Phase 3 — not built yet. The
> type will change to `list[ProductRecord]` once Phase 3 ships.

## Roadmap

- [x] **Phase 0** — Schema & stack
- [x] **Phase 1** — Document ingestion (PDF / DOCX)
- [x] **Phase 2** — CSV/XLSX catalog batch, single-product URL scrape, catalog-listing crawl
- [ ] **Phase 3** — Schema-guided LLM extraction
- [ ] **Phase 4** — Validation layer (per-field confidence, conflict detection)
- [ ] **Phase 5** — Explainability (source citations, extracted/inferred/needs-review)
- [ ] **Phase 6** — Commerce schema mapping (Schema.org / Google Shopping / GS1)
- [ ] **Phase 7** — Demo UI (React)
- [ ] **Phase 8** — Testing & pitch prep

The core differentiator is the validation + explainability work in Phases 4–5:
every extracted field carries a confidence score and a citation back to its
source, so the pipeline is trustworthy, not a black box.

