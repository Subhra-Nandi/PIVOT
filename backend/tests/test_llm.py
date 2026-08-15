"""Phase 3 tests for the LLM client layer: each provider client, and the
Gemini -> Groq -> GitHub Models fallback chain.

Every provider SDK call is monkeypatched — same approach as the Firecrawl
mocking in test_web_ingest.py — so this suite makes zero real network/API
calls and spends zero quota on any provider.

Run: backend/.venv/Scripts/python.exe -m pytest -q
"""

from __future__ import annotations

import pytest

from app.llm.base import LLMError
from app.llm.fallback import FallbackLLMClient
from app.llm.gemini_client import GeminiClient
from app.llm.github_client import GitHubModelsClient
from app.llm.groq_client import GroqClient


# --- GeminiClient ---


def test_gemini_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiClient().complete("prompt")


def test_gemini_client_returns_text(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    from google import genai

    class FakeResponse:
        text = "hello from gemini"

    class FakeModels:
        def generate_content(self, model, contents):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)

    result = GeminiClient().complete("prompt")
    assert result == "hello from gemini"


def test_gemini_client_wraps_sdk_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    from google import genai

    class FakeModels:
        def generate_content(self, model, contents):
            raise RuntimeError("quota exceeded")

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)

    with pytest.raises(LLMError, match="quota exceeded"):
        GeminiClient().complete("prompt")


def test_gemini_client_raises_on_empty_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    from google import genai

    class FakeResponse:
        text = ""

    class FakeModels:
        def generate_content(self, model, contents):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)

    with pytest.raises(LLMError, match="empty response"):
        GeminiClient().complete("prompt")


# --- GroqClient ---


def test_groq_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqClient().complete("prompt")


def test_groq_client_returns_text(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    import groq

    class FakeMessage:
        content = "hello from groq"

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def create(self, model, messages):
            return type("R", (), {"choices": [FakeChoice()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = FakeChat()

    monkeypatch.setattr(groq, "Groq", FakeGroq)

    result = GroqClient().complete("prompt")
    assert result == "hello from groq"


def test_groq_client_wraps_sdk_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    import groq

    class FakeCompletions:
        def create(self, model, messages):
            raise RuntimeError("rate limited")

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = FakeChat()

    monkeypatch.setattr(groq, "Groq", FakeGroq)

    with pytest.raises(LLMError, match="rate limited"):
        GroqClient().complete("prompt")


# --- GitHubModelsClient ---


def test_github_client_raises_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(LLMError, match="GITHUB_TOKEN"):
        GitHubModelsClient().complete("prompt")


def test_github_client_returns_text(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    import openai

    class FakeMessage:
        content = "hello from github models"

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def create(self, model, messages):
            return type("R", (), {"choices": [FakeChoice()]})()

    class FakeChatNS:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = FakeChatNS()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)

    result = GitHubModelsClient().complete("prompt")
    assert result == "hello from github models"


# --- FallbackLLMClient ---


def test_fallback_returns_first_success():
    class Ok:
        def complete(self, prompt):
            return "ok"

    class NeverCalled:
        def complete(self, prompt):
            raise AssertionError("should not be called")

    client = FallbackLLMClient([Ok(), NeverCalled()])
    assert client.complete("prompt") == "ok"


def test_fallback_skips_failed_clients():
    calls = []

    class Fails:
        def complete(self, prompt):
            calls.append("fails")
            raise LLMError("boom")

    class Succeeds:
        def complete(self, prompt):
            calls.append("succeeds")
            return "recovered"

    client = FallbackLLMClient([Fails(), Succeeds()])
    assert client.complete("prompt") == "recovered"
    assert calls == ["fails", "succeeds"]


def test_fallback_raises_when_all_fail():
    class AlwaysFails:
        def complete(self, prompt):
            raise LLMError("nope")

    client = FallbackLLMClient([AlwaysFails(), AlwaysFails()])
    with pytest.raises(LLMError, match="All LLM providers failed"):
        client.complete("prompt")


def test_fallback_requires_at_least_one_client():
    with pytest.raises(ValueError):
        FallbackLLMClient([])
