from app.llm.base import LLMClient, LLMError
from app.llm.fallback import FallbackLLMClient
from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient


def get_default_client() -> LLMClient:
    """Builds the standard Gemini -> Groq fallback chain.

    Each sub-client only raises LLMError at `.complete()` time (lazy key
    check), so an unconfigured provider just fails over to the next one
    rather than crashing here.
    """
    return FallbackLLMClient([GeminiClient(), GroqClient()])


__all__ = [
    "LLMClient",
    "LLMError",
    "FallbackLLMClient",
    "GeminiClient",
    "GroqClient",
    "get_default_client",
]
