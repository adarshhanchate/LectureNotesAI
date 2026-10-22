"""CLI tool to test LLM provider connectivity and discover available models.

Usage:
    python -m backend.llm.check
    python -m backend.llm.check --provider gemini
    python -m backend.llm.check --provider ollama
    python -m backend.llm.check --all
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import List, Optional

# Ensure project root is in sys.path regardless of working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from google import genai

from backend.config import get_settings
from backend.llm.base import (
    DailyQuotaExhaustedError,
    LLMProviderError,
    RateLimitExceededError,
    SetupRequiredError,
)
from backend.llm.gemini_provider import GeminiProvider
from backend.llm.ollama_provider import OllamaProvider


async def check_gemini(settings, recommend_only: bool = False):
    print("\n" + "=" * 60)
    print("   [Gemini Cloud Provider Diagnostic]")
    print("=" * 60)
    has_key = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your-gemini-api-key-here")
    print(f"API Key Configured: {'Yes' if has_key else 'NO (Missing or placeholder)'}")
    print(f"Current GEMINI_MODEL: {settings.GEMINI_MODEL or '(Not configured - will discover models once key is provided)'}")
    print(f"Rate Limit Setting:   {settings.RATE_LIMIT_RPM} req/min")

    if not has_key:
        print("\n[-] SETUP REQUIRED:")
        print("    A Google Gemini API key was not found.")
        print("    1. Obtain a free API key at: https://aistudio.google.com/app/apikey")
        print("    2. Add it to your .env file: GEMINI_API_KEY=AIzaSy...")
        print("    3. Or set LLM_PROVIDER=ollama for local offline processing.")
        return False

    print("\n[*] Connecting to Google Gemini API to query available models for this key...")
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # client.models.list() returns an iterable of models
        models_pager = client.models.list()
        all_models: List[str] = []
        for m in models_pager:
            name = getattr(m, "name", str(m))
            # Format usually 'models/gemini-2.0-flash' or 'gemini-2.0-flash'
            clean_name = name.replace("models/", "")
            all_models.append(clean_name)

        if not all_models:
            print("  [!] API key accepted, but 0 models returned by client.models.list().")
        else:
            print(f"  [+] Found {len(all_models)} total models available to your key.")
            print("\n  Available Gemini Models:")
            for m in sorted(all_models):
                print(f"    - {m}")

        # Filter Flash / Flash-Lite models suitable for free tier
        flash_models = [m for m in all_models if "flash" in m.lower()]
        flash_lite_models = [m for m in flash_models if "lite" in m.lower()]
        standard_flash = [m for m in flash_models if "lite" not in m.lower()]

        print("\n[Free Tier Recommendations (Flash / Flash-Lite)]")
        if flash_models:
            recommended = None
            preferred_order = [
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "gemini-2.5-flash",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
            ]
            for pref in preferred_order:
                if any(pref in m for m in flash_models):
                    recommended = next(m for m in flash_models if pref in m)
                    break
            if not recommended:
                recommended = flash_models[0]

            print(f"  Recommended Model:   {recommended}")
            print(f"  To use this model:   Add `GEMINI_MODEL={recommended}` in your .env file.")
            if settings.GEMINI_MODEL != recommended:
                print(f"  (Note: Your current .env setting is GEMINI_MODEL={settings.GEMINI_MODEL})")
        else:
            print("  No 'flash' models found in account list. You can specify a custom model in GEMINI_MODEL.")

        # Test live ping with configured or recommended model
        target_model = settings.GEMINI_MODEL or recommended
        if target_model:
            print(f"\n[*] Testing live ping with model '{target_model}'...")
            gemini_provider = GeminiProvider(model_name=target_model, api_key=settings.GEMINI_API_KEY)
            res = await gemini_provider.check_connection()
            print("[+] SUCCESS! Gemini connection verified.")
            print(f"    Model Used:   {res.get('model')}")
            print(f"    Latency:      {res.get('latency_ms')} ms")
            print(f"    Response:     {res.get('sample_response')}")
            return True
        else:
            print("\n[!] Please configure GEMINI_MODEL in .env with one of the available models above.")
            return False

    except Exception as e:
        err_msg = str(e)
        if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
            print("\n[-] QUOTA NOTICE: Daily rate limit or quota reached on free tier.")
            print("    Please wait for quota reset or switch to Local (Ollama) mode.")
        elif "API_KEY_INVALID" in err_msg or "INVALID_ARGUMENT" in err_msg or "400" in err_msg:
            print(f"\n[-] AUTH ERROR: Invalid Gemini API key ({err_msg}).")
        else:
            print(f"\n[-] GEMINI ERROR: {type(e).__name__}: {err_msg}")
        return False


async def check_ollama(settings):
    print("\n" + "=" * 60)
    print("   [Ollama Local Provider Diagnostic]")
    print("=" * 60)
    print(f"Base URL:              {settings.OLLAMA_BASE_URL}")
    print(f"Default Model (7b):    {settings.OLLAMA_MODEL}")
    print(f"Fast Mode Model (3b):  {settings.OLLAMA_FAST_MODEL}")

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            if resp.status_code != 200:
                print(f"[-] Ollama returned HTTP {resp.status_code}")
                return False

            data = resp.json()
            models = [m.get("name") for m in data.get("models", [])]
            print(f"[+] Ollama daemon is running. Found {len(models)} local model(s):")
            if models:
                for m in models:
                    print(f"    - {m}")
            else:
                print("    (No models installed yet)")

            has_7b = any(settings.OLLAMA_MODEL in m for m in models)
            has_3b = any(settings.OLLAMA_FAST_MODEL in m for m in models)

            print("\n[Model Status]")
            print(f"  Standard 7b ({settings.OLLAMA_MODEL}):     {'[READY]' if has_7b else '[MISSING - Run: ollama pull ' + settings.OLLAMA_MODEL + ']'}")
            print(f"  Fast Mode 3b ({settings.OLLAMA_FAST_MODEL}): {'[READY]' if has_3b else '[MISSING - Run: ollama pull ' + settings.OLLAMA_FAST_MODEL + ']'}")

            # Test generation with whatever model is available
            test_model = settings.OLLAMA_MODEL if has_7b else (settings.OLLAMA_FAST_MODEL if has_3b else None)
            if test_model:
                print(f"\n[*] Testing generation ping with '{test_model}'...")
                provider = OllamaProvider(model_name=test_model, base_url=settings.OLLAMA_BASE_URL)
                t0 = time.monotonic()
                ping_res = await provider.generate_text("Reply with 'PONG' only.")
                latency_ms = int((time.monotonic() - t0) * 1000)
                print("[+] SUCCESS! Ollama local generation working.")
                print(f"    Model:    {test_model}")
                print(f"    Latency:  {latency_ms} ms")
                print(f"    Response: {ping_res.strip()}")
                return True
            else:
                print("\n[!] Cannot run generation ping because neither 7b nor 3b is pulled.")
                print(f"    Please run: `ollama pull {settings.OLLAMA_FAST_MODEL}` for fast low-memory mode.")
                return False

    except httpx.ConnectError:
        print(f"\n[-] Ollama is NOT running at {settings.OLLAMA_BASE_URL}.")
        print("    Start it with `ollama serve` in a terminal.")
        return False
    except Exception as e:
        print(f"\n[-] Ollama error: {type(e).__name__}: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Test LLM provider connectivity and list available models.")
    parser.add_argument("--provider", choices=["gemini", "ollama"], help="Specific provider to test")
    parser.add_argument("--all", action="store_true", help="Test both Gemini and Ollama")
    args = parser.parse_args()

    settings = get_settings()

    if args.all:
        await check_gemini(settings)
        await check_ollama(settings)
    elif args.provider:
        if args.provider == "gemini":
            await check_gemini(settings)
        else:
            await check_ollama(settings)
    else:
        # Default: check configured provider
        if settings.LLM_PROVIDER == "gemini":
            await check_gemini(settings)
        elif settings.LLM_PROVIDER == "ollama":
            await check_ollama(settings)
        else:
            await check_gemini(settings)
            await check_ollama(settings)


if __name__ == "__main__":
    asyncio.run(main())
