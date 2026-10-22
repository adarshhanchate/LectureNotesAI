"""Gemini LLM Provider using the official google-genai SDK."""

import json
import logging
import re
import time
from typing import Optional, Dict, Any

from google import genai
from google.genai import types

from backend.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    SetupRequiredError,
)
from backend.llm.rate_limiter import AsyncRateLimiter, execute_with_backoff
from backend.config import get_settings

logger = logging.getLogger("lecturenotes.llm.gemini")


def clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Strip markdown code fences and parse JSON safely, repairing invalid LaTeX escapes."""
    text = raw_text.strip()
    # Remove markdown code fences if present
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()

    # 1. Direct JSON parse attempt
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Repair unescaped backslashes from LaTeX (e.g., \Delta, \frac, \alpha)
    try:
        fixed = re.sub(r'\\(?![/"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 3. Try finding substring between outermost '{' and '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            try:
                fixed_candidate = re.sub(r'\\(?![/"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', candidate)
                return json.loads(fixed_candidate)
            except json.JSONDecodeError:
                pass

    logger.error(f"Failed to parse JSON from LLM response. Raw content:\n{text[:500]}")
    raise LLMProviderError(f"Could not parse valid JSON from Gemini output: {text[:200]}")


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Cloud Provider using google-genai SDK."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.GEMINI_MODEL
        self.api_key = api_key or settings.GEMINI_API_KEY
        
        # Verify key
        if not self.api_key or self.api_key.strip() in ("", "your-gemini-api-key-here", "your-api-key-here"):
            if not settings.DEMO_MODE:
                raise SetupRequiredError(
                    "Gemini API key is missing. Please set GEMINI_API_KEY in your .env file, "
                    "or switch AI Engine to Local (Ollama) in Advanced Settings."
                )

        if not self.model_name and not settings.DEMO_MODE:
            raise SetupRequiredError(
                "GEMINI_MODEL is not configured in .env. "
                "Run `python -m backend.llm.check` to list available models for your API key and set GEMINI_MODEL."
            )

        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.rate_limiter = AsyncRateLimiter(requests_per_minute=settings.RATE_LIMIT_RPM)

    async def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call Gemini asynchronously with rate limiting and exponential backoff."""
        if not self.client:
            raise SetupRequiredError("Gemini client not initialized. Valid GEMINI_API_KEY is required.")

        config = types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = system_prompt

        FALLBACK_MODELS = [
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-2.5-flash",
        ]
        models_to_try = [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]

        async def _do_generate():
            last_err = None
            for model_candidate in models_to_try:
                try:
                    response = await self.client.aio.models.generate_content(
                        model=model_candidate,
                        contents=prompt,
                        config=config,
                    )
                    if not response.text:
                        raise LLMProviderError("Gemini returned an empty response.")
                    if model_candidate != self.model_name:
                        logger.warning(
                            f"Gemini switched from '{self.model_name}' to working model '{model_candidate}'."
                        )
                        self.model_name = model_candidate
                    return response.text
                except Exception as err:
                    err_msg = str(err).lower()
                    if any(code in err_msg for code in ("404", "not_found", "not found", "503", "unavailable", "high demand")):
                        logger.warning(
                            f"Gemini model '{model_candidate}' unavailable ({err}). Trying next fallback model candidate..."
                        )
                        last_err = err
                        continue
                    # Re-raise other errors (e.g. 429 quota or network) to backoff handler
                    raise err
            if last_err:
                raise last_err
            raise LLMProviderError("All Gemini model candidates failed.")

        return await execute_with_backoff(
            _do_generate,
            rate_limiter=self.rate_limiter,
        )

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text from Gemini."""
        return await self._call_gemini(prompt, system_prompt)

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured JSON from Gemini."""
        instruction = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "IMPORTANT: You MUST respond ONLY with valid JSON. Do not include introductory text, explanations, or backticks outside the JSON."
        )
        raw_text = await self._call_gemini(prompt, instruction)
        return clean_json_response(raw_text)

    async def check_connection(self) -> Dict[str, Any]:
        """Ping Gemini to verify connectivity and API key validity."""
        t0 = time.monotonic()
        response_text = await self.generate_text("Respond with 'PONG' and nothing else.")
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "ok",
            "provider": "gemini",
            "model": self.model_name,
            "latency_ms": latency_ms,
            "sample_response": response_text.strip(),
        }
