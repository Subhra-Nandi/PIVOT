"""Gemini client — primary provider (free tier, per Phase 0's stack choice).

`GEMINI_API_KEY`/`GEMINI_MODEL` are read lazily inside `complete()`, not at
construction time, so building a `GeminiClient()` never fails just because the
key is unset — only calling it does. This is what lets `FallbackLLMClient`
hold all three provider clients unconditionally and let each one fail over to
the next at call time.
"""

from __future__ import annotations

from app.config import get_env
from app.llm.base import LLMError

_DEFAULT_MODEL = "gemini-2.5-flash"  # gemini-2.0-flash was retired (404s as of 2026-08) — verified live


class GeminiClient:
    def complete(self, prompt: str) -> str:
        api_key = get_env("GEMINI_API_KEY")
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set.")

        from google import genai  # imported lazily: optional dep for callers that never reach Gemini

        model_name = get_env("GEMINI_MODEL", _DEFAULT_MODEL)
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model=model_name, contents=prompt)
        except Exception as exc:  # the SDK raises various google.genai.errors exceptions
            raise LLMError(f"Gemini completion failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMError("Gemini returned an empty response.")
        return text
