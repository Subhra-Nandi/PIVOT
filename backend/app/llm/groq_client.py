"""Groq client — fallback provider when Gemini's free quota is exhausted."""

from __future__ import annotations

from app.config import get_env
from app.llm.base import LLMError

_DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqClient:
    def complete(self, prompt: str) -> str:
        api_key = get_env("GROQ_API_KEY")
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set.")

        from groq import Groq  # imported lazily: optional dep for callers that never reach Groq

        model_name = get_env("GROQ_MODEL", _DEFAULT_MODEL)
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # Groq SDK raises groq.APIError and friends
            raise LLMError(f"Groq completion failed: {exc}") from exc

        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise LLMError("Groq returned an empty response.")
        return text
