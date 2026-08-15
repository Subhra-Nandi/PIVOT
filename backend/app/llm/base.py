"""Provider-agnostic LLM interface.

One method — `complete(prompt) -> str` — is all Phase 3 extraction needs.
Keeping the surface this small is what makes `FallbackLLMClient` (Gemini ->
Groq -> GitHub Models) possible without touching extraction logic when a
provider's quota runs out mid-demo.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Raised by any LLMClient when it can't produce a completion — missing
    API key, SDK/network failure, or a rate limit. Callers (namely
    `FallbackLLMClient`) catch this uniformly regardless of provider."""


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        """Send `prompt` to the model, return its raw text response.

        Raises LLMError on any failure — callers never need to know which
        provider-specific exception type to catch.
        """
        ...
