"""Transcript Compound Caching by Audio Hash, Whisper Model, and Language.

Prevents redundant STT compute on the CPU. Re-transcribing the same audio with
the same Whisper model instantly retrieves the cached transcript (0.0s).
"""

from __future__ import annotations
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from backend.config import get_settings

logger = logging.getLogger("lecturenotes.cache")


def compute_file_hash(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_compound_key(
    file_hash: str,
    whisper_model: str = "small",
    language: Optional[str] = None,
) -> str:
    """Compute a compound cache key incorporating file content hash and STT settings."""
    raw = f"{file_hash}:{whisper_model}:{language or 'auto'}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TranscriptCache:
    """Disk-backed compound cache for transcriptions."""

    def __init__(self, cache_dir: Optional[Path] = None):
        settings = get_settings()
        self.cache_dir = cache_dir or settings.TRANSCRIPT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(
        self,
        file_hash: str,
        whisper_model: str = "small",
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached transcript data if available using compound key."""
        compound_key = compute_compound_key(file_hash, whisper_model, language)
        path = self._get_cache_path(compound_key)
        
        # Check auto key or legacy file_hash if specific key not found
        if not path.exists():
            auto_key = compute_compound_key(file_hash, whisper_model, None)
            if self._get_cache_path(auto_key).exists():
                path = self._get_cache_path(auto_key)
            else:
                legacy_path = self._get_cache_path(file_hash)
                if legacy_path.exists():
                    path = legacy_path

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Transcript cache HIT for key {compound_key[:12]} (file {file_hash[:8]})...")
                return data
            except Exception as e:
                logger.warning(f"Failed to read cache file {path}: {e}")
                return None
        return None

    def set(
        self,
        file_hash: str,
        transcript_data: Dict[str, Any],
        whisper_model: str = "small",
        language: Optional[str] = None,
    ) -> None:
        """Store transcript data in cache under compound key."""
        keys = [compute_compound_key(file_hash, whisper_model, language)]
        if language:
            keys.append(compute_compound_key(file_hash, whisper_model, None))

        for compound_key in set(keys):
            path = self._get_cache_path(compound_key)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(transcript_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Cached transcript for compound key {compound_key[:12]} at {path}")
            except Exception as e:
                logger.warning(f"Failed to write cache file {path}: {e}")
