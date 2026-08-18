"""Every app.* submodule must import cleanly on its own, in a fresh
interpreter, regardless of what pytest has already warmed in-process.
Guards against circular imports that pytest's alphabetical test collection
order can otherwise mask.

History: this test used to hand-list "entry point" modules (the
catalog_crawler.py extract_product cycle). That list didn't include
app.ingestion.catalog, which had the *same* circular-import bug via a
different pair of top-level imports (app.validation <-> app.ingestion) and
went undetected for a full review pass. Discovering every submodule
automatically, instead of maintaining a list by hand, is what closes that
gap -- a new module with the same mistake gets caught without anyone
remembering to add it here.
"""

from __future__ import annotations

import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

import app

_ALL_MODULES = sorted(
    info.name
    for info in pkgutil.walk_packages(app.__path__, prefix="app.")
)


@pytest.mark.parametrize("module", _ALL_MODULES)
def test_module_imports_cleanly_in_isolation(module):
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr