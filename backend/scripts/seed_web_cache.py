"""Pre-warm the web ingestion cache from committed fixtures — run before a demo
so `ingest_url()` hits cache for the verified demo URLs even with no network.

Usage: backend/.venv/Scripts/python.exe scripts/seed_web_cache.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.url_ingest import seed_cache_from_fixture

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "web")

# url -> fixture filename. Keep in sync with the verified demo sources in
# .response/phase-2-plan.md.
_DEMO_SOURCES = {
    "https://www.sparkfun.com/sparkx-power-meter-acs37800-qwiic.html": "sparkfun_acs37800.html",
    "https://www.adafruit.com/product/2471": "adafruit_2471.html",
    "https://www.boltdepot.com/Product-Details?product=54": "boltdepot_54.html",
}


def main() -> None:
    for url, filename in _DEMO_SOURCES.items():
        fixture_path = os.path.join(_FIXTURES_DIR, filename)
        document = seed_cache_from_fixture(url, fixture_path)
        print(f"seeded {url} <- {filename} ({len(document.blocks)} blocks)")


if __name__ == "__main__":
    main()
