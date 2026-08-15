"""Tries each configured LLMClient in order, falling through on failure.

This is the piece that makes the Phase 0 "hitting a rate limit mid-demo
shouldn't require touching extraction logic" goal real: extraction code only
ever talks to one `LLMClient`, and this class is the one that's actually
handed to it by default.
"""

from __future__ import annotations

from app.llm.base import LLMClient, LLMError


class FallbackLLMClient:
    def __init__(self, clients: list[LLMClient]) -> None:
        if not clients:
            raise ValueError("FallbackLLMClient needs at least one client.")
        self._clients = clients

    def complete(self, prompt: str) -> str:
        errors: list[str] = []
        for client in self._clients:
            try:
                return client.complete(prompt)
            except LLMError as exc:
                errors.append(f"{type(client).__name__}: {exc}")
        raise LLMError(
            "All LLM providers failed: " + "; ".join(errors)
        )
