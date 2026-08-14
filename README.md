# PIVOT

**Product Intelligence & Validation for Optimized Trade**

AI-powered product intelligence for industrial commerce: turn scattered product
data (PDFs, catalogs, websites) into structured, validated, commerce-ready
product records — with every field traceable back to its source.

> Team project — Hack2Skill

## Status

**Phase 0 complete.** The domain-agnostic product schema and the validation
attribute dictionary are in place and tested. The FastAPI `/extract` endpoint,
the ingestion pipelines, and the React demo UI arrive in later phases — see the
[Roadmap](#roadmap). Right now the repo is the schema layer plus its test suite.

## Prerequisites

- **Python 3.12+**
- **Git**
- Node.js — only needed once the React frontend lands (Phase 7), not yet.

## Getting started (backend)

All backend work happens in `backend/`.

```bash
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

If you see `7 passed`, the schema layer is working and you're ready to build.

> **PowerShell blocks `Activate.ps1`?** Run once per terminal session:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
> — or skip activation and call the venv Python directly:
> `.venv\Scripts\python.exe -m pytest -q`

## Environment variables

The LLM extraction layer (Phase 3) uses free-tier providers behind one swappable
interface: **Gemini** (primary) → **Groq** (fallback) → **GitHub Models** (tertiary).

```bash
# from the repo root
cp .env.example .env        # Windows: copy .env.example .env
```

Then fill in whatever keys you have. `.env` is gitignored — never commit it.
Free keys come from:

- **Gemini** — Google AI Studio (aistudio.google.com); use Flash / Flash-Lite, not Pro
- **Groq** — console.groq.com
- **GitHub Models** — a GitHub personal access token

You don't need any keys to run the current schema and tests.

## Project structure

```
PIVOT/
├── backend/
│   ├── app/
│   │   └── schemas/
│   │       ├── product.py      # ProductRecord — the single source of truth
│   │       └── attributes.py   # attribute dictionary used for validation
│   ├── tests/                  # pytest suite guarding the schema contract
│   └── requirements.txt
├── .env.example                # copy to .env, add LLM keys
└── README.md
```

`schemas/product.py` is the one file everything else derives from: FastAPI
validates against it, the LLM extraction layer targets its JSON Schema, and the
validation/explainability layers populate its confidence and source fields.

## Roadmap

- [x] **Phase 0** — Schema & stack
- [ ] **Phase 1** — Document ingestion (PDF / DOCX / catalogs)
- [ ] **Phase 2** — Website ingestion (MCP-based)
- [ ] **Phase 3** — Schema-guided LLM extraction
- [ ] **Phase 4** — Validation layer (per-field confidence, conflict detection)
- [ ] **Phase 5** — Explainability (source citations, extracted/inferred/needs-review)
- [ ] **Phase 6** — Commerce schema mapping (Schema.org / Google Shopping / GS1)
- [ ] **Phase 7** — Demo UI (React)
- [ ] **Phase 8** — Testing & pitch prep

The core differentiator is the validation + explainability work in Phases 4–5:
every extracted field carries a confidence score and a citation back to its
source, so the pipeline is trustworthy, not a black box.
