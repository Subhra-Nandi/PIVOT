"""Central `.env` bootstrap.

Every other module reads provider keys lazily via `os.environ.get(...)`
(the same pattern `web_fetcher.py`/`catalog_crawler.py` already use for
`FIRECRAWL_API_KEY`) — this module's only job is to make sure `.env` has
actually been loaded into `os.environ` before any of those lookups happen.
`load_dotenv()` is idempotent and cheap, so calling it at import time here is
safe even if multiple modules import `app.config`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default: str | None = None) -> str | None:
    """Thin wrapper over `os.environ.get` — exists so callers don't need to
    import `os` just to read one var, and so `.env` loading stays centralized
    here rather than duplicated per module."""
    return os.environ.get(name, default)
