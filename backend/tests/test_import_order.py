"""Each app.* entry point must import cleanly on its own, in a fresh
interpreter, regardless of what pytest has already warmed in-process.
Guards against circular imports that pytest's alphabetical test collection
order can otherwise mask (see catalog_crawler.py's history)."""

from __future__ import annotations

import subprocess
import sys

import pytest

ENTRY_POINTS = [
    "app.extraction.extractor",
    "app.explainability",
    "app.ingestion",
    "app.ingestion.catalog_crawler",
]


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_module_imports_cleanly_in_isolation(module):
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr