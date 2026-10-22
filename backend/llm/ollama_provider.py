"""Ollama Local LLM Provider for offline & privacy-focused inference."""

import json
import logging
import re
import time
from typing import Optional, Dict, Any
import httpx

from backend.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    SetupRequiredError,
)
from backend.config import get_settings

logger = logging.getLogger("lecturenotes.llm.ollama")


def clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Strip markdown code fences and parse JSON safely, repairing invalid LaTeX escapes."""
    text = raw_text.strip()
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

    logger.error(f"Failed to parse JSON from Ollama output. Raw content:\n{text[:500]}")
    raise LLMProviderError(f"Could not parse valid JSON from Ollama output: {text[:200]}")


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider tuned for low-end hardware (16GB RAM / Intel Iris)."""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.OLLAMA_MODEL
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.num_ctx = 4096
        self.temperature = 0.2
        self.keep_alive = "5m"

    async def _call_ollama(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> str:
        """Call Ollama /api/generate asynchronously with hardware-tuned options."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": self.temperature,
                "num_thread": 8,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        # Extended timeout for CPU inference (up to 15 mins for large 7B models on CPU)
        timeout = httpx.Timeout(connect=15.0, read=900.0, write=60.0, pool=15.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                
                if resp.status_code == 404:
                    raise SetupRequiredError(
                        f"Model '{self.model_name}' not found in Ollama. "
                        f"Run `ollama pull {self.model_name}` in your terminal."
                    )
                if resp.status_code != 200:
                    raise LLMProviderError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

                data = resp.json()
                response_text = data.get("response", "")
                if not response_text:
                    raise LLMProviderError("Ollama returned an empty response.")
                return response_text

        except httpx.ConnectError as e:
            raise SetupRequiredError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running (`ollama serve`), or switch AI Engine to Gemini (Cloud)."
            ) from e
        except httpx.ReadTimeout as e:
            raise LLMProviderError(
                f"Ollama inference timed out after 300s. The model '{self.model_name}' may be too large for CPU inference. "
                "Try Fast Mode (qwen2.5:3b) or switch to Gemini Cloud."
            ) from e

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text from Ollama."""
        return await self._call_ollama(prompt, system_prompt, format_json=False)

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured JSON from Ollama with format='json'."""
        instruction = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "Respond strictly with valid JSON. Do not include markdown codeblocks or conversational text."
        )
        raw_text = await self._call_ollama(prompt, instruction, format_json=True)
        return clean_json_response(raw_text)

    async def check_connection(self) -> Dict[str, Any]:
        """Ping Ollama to verify daemon is alive and model is available."""
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                tags_resp = await client.get(f"{self.base_url}/api/tags")
                if tags_resp.status_code != 200:
                    raise LLMProviderError(f"Ollama /api/tags returned HTTP {tags_resp.status_code}")
                tags_data = tags_resp.json()
                available_models = [m.get("name") for m in tags_data.get("models", [])]
                
                # Check if configured model is available
                model_matches = any(
                    self.model_name in m or m.startswith(self.model_name.split(":")[0])
                    for m in available_models
                )
                if not model_matches:
                    raise SetupRequiredError(
                        f"Ollama is running, but model '{self.model_name}' is not pulled. "
                        f"Available models: {', '.join(available_models) if available_models else 'none'}. "
                        f"Run: `ollama pull {self.model_name}`."
                    )
        except httpx.ConnectError as e:
            raise SetupRequiredError(
                f"Ollama is NOT running at {self.base_url}. Start it with `ollama serve` or switch to Gemini."
            ) from e

        # Quick generation test
        await self.generate_text("Reply with 'PONG' only.")
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "ok",
            "provider": "ollama",
            "model": self.model_name,
            "latency_ms": latency_ms,
        }
