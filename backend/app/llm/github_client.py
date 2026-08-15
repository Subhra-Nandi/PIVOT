"""GitHub Models client — tertiary fallback (small context window, per
Phase 0's stack choice).

GitHub Models exposes an OpenAI-compatible chat-completions endpoint, so this
reuses the `openai` SDK pointed at GitHub's inference base_url rather than
writing a bespoke HTTP client.
"""

from __future__ import annotations

from app.config import get_env
from app.llm.base import LLMError

_DEFAULT_MODEL = "gpt-4o-mini"
_GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


class GitHubModelsClient:
    def complete(self, prompt: str) -> str:
        token = get_env("GITHUB_TOKEN")
        if not token:
            raise LLMError("GITHUB_TOKEN is not set.")

        from openai import OpenAI  # imported lazily: optional dep for callers that never reach GitHub Models

        model_name = get_env("GITHUB_MODEL", _DEFAULT_MODEL)
        try:
            client = OpenAI(api_key=token, base_url=_GITHUB_MODELS_BASE_URL)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # openai SDK raises openai.APIError and friends
            raise LLMError(f"GitHub Models completion failed: {exc}") from exc

        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise LLMError("GitHub Models returned an empty response.")
        return text
