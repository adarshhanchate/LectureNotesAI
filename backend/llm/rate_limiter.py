"""Async Token Bucket Rate Limiter with Exponential Backoff and Jitter."""

import asyncio
import logging
import random
import time
from typing import Callable, Any
from backend.llm.base import RateLimitExceededError, DailyQuotaExhaustedError

logger = logging.getLogger("lecturenotes.llm.rate_limiter")


class AsyncRateLimiter:
    """Token-bucket rate limiter for LLM API calls."""

    def __init__(self, requests_per_minute: int = 10):
        self.rpm = max(1, requests_per_minute)
        self.interval = 60.0 / self.rpm
        self.lock = asyncio.Lock()
        self.last_call_time = 0.0

    async def acquire(self):
        """Wait until a request can be dispatched according to the rate limit."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_call_time
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                logger.debug(f"Rate limiter pacing: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self.last_call_time = time.monotonic()


async def execute_with_backoff(
    func: Callable,
    *args,
    rate_limiter: AsyncRateLimiter = None,
    max_retries: int = 4,
    base_delay: float = 2.0,
    **kwargs,
) -> Any:
    """Execute an async function with token bucket pacing and exponential backoff with jitter on 429 / RESOURCE_EXHAUSTED."""
    for attempt in range(max_retries + 1):
        if rate_limiter:
            await rate_limiter.acquire()
            
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(
                code in err_str
                for code in ["429", "resource_exhausted", "rate limit", "too many requests"]
            )
            is_quota = any(
                q in err_str
                for q in ["quota exceeded", "daily limit", "check your plan and billing", "insufficient_quota"]
            )

            if is_quota:
                logger.error(f"Daily quota exhausted: {e}")
                raise DailyQuotaExhaustedError(
                    "Google Gemini daily free-tier quota has been exhausted. "
                    "Please switch AI Engine to Local (Ollama) in Advanced Settings or retry tomorrow."
                ) from e

            if is_rate_limit:
                if attempt == max_retries:
                    logger.error(f"Rate limit exceeded after {max_retries} retries: {e}")
                    raise RateLimitExceededError(
                        f"LLM API rate limit exceeded after {max_retries} attempts. "
                        "Please wait a moment before trying again or switch to Local (Ollama)."
                    ) from e

                # Exponential backoff with jitter
                delay = (base_delay * (2 ** attempt)) + random.uniform(0.5, 2.0)
                logger.warning(
                    f"Rate limited (attempt {attempt + 1}/{max_retries}). "
                    f"Backing off for {delay:.2f}s with jitter..."
                )
                await asyncio.sleep(delay)
            else:
                # Other non-rate-limit exception
                raise e
