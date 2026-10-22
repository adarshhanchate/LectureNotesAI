"""Abstract Base LLM Provider definition."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class RateLimitExceededError(LLMProviderError):
    """Raised when rate limits are exceeded."""
    pass


class DailyQuotaExhaustedError(LLMProviderError):
    """Raised when provider daily free quota is fully exhausted."""
    pass


class SetupRequiredError(LLMProviderError):
    """Raised when required credentials or local servers are not configured."""
    pass


class BaseLLMProvider(ABC):
    """Abstract interface that all LLM providers must implement."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text completion from prompt."""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured JSON response from prompt."""
        pass

    @abstractmethod
    async def check_connection(self) -> Dict[str, Any]:
        """Test provider connectivity and return diagnostic info."""
        pass
