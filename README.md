# PIVOT

**Product Intelligence & Validation for Optimized Trade**

AI-powered product intelligence for industrial commerce: turn scattered product
data (PDFs, catalogs, websites) into structured, validated, commerce-ready
product records — with every field traceable back to its source.
> Team project — Hack2Skill

## Status

**Phase 0, Phase 1, Phase 2, and Phase 3 complete.** The domain-agnostic
product schema and the validation attribute dictionary are in place and
tested (Phase 0). The document ingestion pipeline — PDF and DOCX parsing into
a common structured intermediate format, with page/section references
preserved for later citation — is also in place and tested (Phase 1).
Phase 2 adds three more ingestion paths: CSV/XLSX catalog batches mapped
directly to product records (no LLM), single-product URL scraping (static
fetch with a Firecrawl fallback for JS-heavy/bot-walled sites), and
catalog-listing crawling that discovers product links and enriches them page
by page. Phase 3 closes the loop for the two source types that need an LLM
(documents and web pages): schema-guided extraction turns an `IngestedDocument`
into a real `ProductRecord`, via a swappable Gemini → Groq → GitHub Models
fallback chain, live-verified against a real Gemini call. The FastAPI
`/extract` endpoint and the React demo UI arrive in later phases — see the
[Roadmap](#roadmap).

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

If you see `70 passed`, the schema layer, all three ingestion paths
(documents, catalogs, web), and LLM extraction are working and you're ready
to build. The suite makes zero real network/LLM calls — every provider SDK
call is mocked, same as the Firecrawl mocking from Phase 2.
> **PowerShell blocks `Activate.ps1`?** Run once per terminal session: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` — or skip activation and call the venv Python directly: `.venv\Scripts\python.exe -m pytest -q`

## Environment variables

The LLM extraction layer (Phase 3) uses free-tier providers behind one swappable
interface: **Gemini** (primary) → **Groq** (fallback) → **GitHub Models** (tertiary).
`app/config.py` loads `.env` automatically (via `python-dotenv`) the first time
any app module is imported — you don't need to `export` anything yourself.

```
# from the repo root
cp .env.example .env        # Windows: copy .env.example .env
```

Then fill in whatever keys you have. `.env` is gitignored — never commit it.
Free keys come from:

- **Gemini** — Google AI Studio (aistudio.google.com/apikey); use Flash /
  Flash-Lite, not Pro. **Only this one is required** to actually run
  extraction (`extract_product()`) — Groq/GitHub Models are fallbacks for
  when Gemini's quota runs out, and the pipeline works without them.
  Current default model is `gemini-2.5-flash` — `gemini-2.0-flash` was
  retired by Google and now 404s, so don't reuse an old key/model pairing
  from another project.
- **Groq** — console.groq.com (optional — fallback only)
- **GitHub Models** — a GitHub personal access token (optional — fallback only)
- **Firecrawl** — firecrawl.dev; only needed as a fallback for JS-heavy or
  bot-walled product pages and for catalog-listing crawls. Single-page static
  scraping and CSV/XLSX/PDF/DOCX ingestion work without it.

You don't need any keys to run the schema, ingestion pipeline, and the test
suite (LLM calls are mocked in tests). You need `GEMINI_API_KEY` to actually
run `extract_product()` against a real document or web page.

## Project structure

```
PIVOT/
├── backend/
│   ├── app/
│   │   ├── config.py               # loads .env once via python-dotenv; get_env() helper
│   │   ├── schemas/
│   │   │   ├── product.py          # ProductRecord — the single source of truth
│   │   │   └── attributes.py       # attribute dictionary used for validation
│   │   ├── ingestion/
│   │   │   ├── models.py           # IngestedDocument / ContentBlock — intermediate format
│   │   │   ├── pdf_parser.py       # PDF text + table extraction (pdfplumber)
│   │   │   ├── docx_parser.py      # DOCX text + table extraction (python-docx)
│   │   │   ├── base.py             # ingest_document() — PDF/DOCX dispatch entrypoint
│   │   │   ├── catalog.py          # ingest_catalog() — CSV/XLSX → ProductRecord, no LLM
│   │   │   ├── web_fetcher.py      # fetch_html() — static fetch + Firecrawl fallback
│   │   │   ├── web_parser.py       # parse_html() — JSON-LD/tables/text → IngestedDocument
│   │   │   ├── url_ingest.py       # ingest_url() — single-product-URL entrypoint + cache
│   │   │   ├── catalog_crawler.py  # ingest_catalog_url() — listing discovery + enrichment
│   │   │   └── utils.py            # shared parsing helpers
│   │   ├── llm/
│   │   │   ├── base.py             # LLMClient protocol + LLMError
│   │   │   ├── gemini_client.py    # GeminiClient — primary provider
│   │   │   ├── groq_client.py      # GroqClient — fallback
│   │   │   ├── github_client.py    # GitHubModelsClient — tertiary fallback
│   │   │   └── fallback.py         # FallbackLLMClient — tries each in order
│   │   └── extraction/
│   │       ├── prompt.py           # build_extraction_prompt() — schema-guided prompt
│   │       └── extractor.py        # extract_product() — IngestedDocument → ProductRecord
│   ├── fixtures/
│   │   ├── catalogs/               # committed demo_catalog.csv
│   │   └── web/                    # committed raw HTML for the verified demo URLs
│   ├── scripts/
│   │   └── seed_web_cache.py       # pre-warms the web cache from fixtures before a demo
│   ├── tests/                      # pytest suite guarding every layer above
│   └── requirements.txt
├── .env.example                    # copy to .env, add LLM/Firecrawl keys
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

`extraction/extractor.py`'s `extract_product(doc)` is what turns an
`IngestedDocument` (from PDF, DOCX, or a web page) into a real `ProductRecord`:
it builds a schema-guided prompt (`extraction/prompt.py`) that includes the
full `ProductRecord` JSON schema plus every content block tagged with its
`block_id`/`page`/`section`, calls the LLM, validates the JSON response, and
retries once on failure before raising. `ingest_catalog_url()`'s
`CatalogResult.enriched` now returns `list[ProductRecord]` — each discovered
product page is scraped via `ingest_url()` and then run through
`extract_product()`.

`llm/` is the provider layer behind `extract_product()`: one `LLMClient`
interface (`complete(prompt) -> str`), three implementations (Gemini, Groq,
GitHub Models), and a `FallbackLLMClient` that tries them in order so a
rate limit on one provider doesn't require touching extraction code —
just add the next provider's key.

## Roadmap

- [x] **Phase 0** — Schema & stack
- [x] **Phase 1** — Document ingestion (PDF / DOCX)
- [x] **Phase 2** — CSV/XLSX catalog batch, single-product URL scrape, catalog-listing crawl
- [x] **Phase 3** — Schema-guided LLM extraction (Gemini → Groq → GitHub Models)
- [ ] **Phase 4** — Validation layer (per-field confidence, conflict detection)
- [ ] **Phase 5** — Explainability (source citations, extracted/inferred/needs-review)
- [ ] **Phase 6** — Commerce schema mapping (Schema.org / Google Shopping / GS1)
- [ ] **Phase 7** — Demo UI (React)
- [ ] **Phase 8** — Testing & pitch prep

The core differentiator is the validation + explainability work in Phases 4–5:
every extracted field carries a confidence score and a citation back to its
source, so the pipeline is trustworthy, not a black box.

