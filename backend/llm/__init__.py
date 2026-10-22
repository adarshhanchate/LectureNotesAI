"""LLM Provider Factory and Export Interface."""

import logging
from typing import Optional

from backend.config import get_settings
from backend.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    RateLimitExceededError,
    DailyQuotaExhaustedError,
    SetupRequiredError,
)
from backend.llm.gemini_provider import GeminiProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.llm.demo_provider import DemoProvider

logger = logging.getLogger("lecturenotes.llm")


def get_llm_provider(
    provider_type: Optional[str] = None,
    model_name: Optional[str] = None,
    fast_mode: bool = False,
) -> BaseLLMProvider:
    """Factory to get the configured LLM provider.

    provider_type: 'gemini' | 'ollama' | None (falls back to settings.LLM_PROVIDER).
    """
    settings = get_settings()
    provider_str = (provider_type or settings.LLM_PROVIDER).strip().lower()

    # Map legacy aliases
    if provider_str in ("google", "gemini-cloud"):
        provider_str = "gemini"
    elif provider_str in ("local", "ollama-local"):
        provider_str = "ollama"

    if provider_str == "gemini":
        try:
            return GeminiProvider(model_name=model_name or settings.GEMINI_MODEL)
        except SetupRequiredError as e:
            if settings.DEMO_MODE:
                logger.warning(f"Gemini setup failed ({e}), falling back to DemoProvider because DEMO_MODE=True.")
                return DemoProvider()
            raise e

    elif provider_str == "ollama":
        try:
            resolved_model = model_name or (settings.OLLAMA_FAST_MODEL if fast_mode else settings.OLLAMA_MODEL)
            return OllamaProvider(
                model_name=resolved_model,
                base_url=settings.OLLAMA_BASE_URL,
            )
        except SetupRequiredError as e:
            if settings.DEMO_MODE:
                logger.warning(f"Ollama setup failed ({e}), falling back to DemoProvider because DEMO_MODE=True.")
                return DemoProvider()
            raise e

    elif provider_str == "demo":
        if not settings.DEMO_MODE:
            raise SetupRequiredError("Demo provider requested, but DEMO_MODE is false in configuration.")
        return DemoProvider()

    else:
        raise LLMProviderError(
            f"Unsupported LLM provider: '{provider_str}'. Supported providers are: 'gemini', 'ollama'."
        )


__all__ = [
    "BaseLLMProvider",
    "GeminiProvider",
    "OllamaProvider",
    "DemoProvider",
    "get_llm_provider",
    "LLMProviderError",
    "RateLimitExceededError",
    "DailyQuotaExhaustedError",
    "SetupRequiredError",
]
