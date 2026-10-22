"""Transcription module — uses faster-whisper on CPU (int8) with memory isolation."""

from __future__ import annotations
import asyncio
import gc
import logging
from pathlib import Path
from typing import Tuple, List, Callable, Optional, Dict, Any

from backend.models import TranscriptSegment
from backend.config import get_settings
from backend.pipeline.cache import TranscriptCache, compute_file_hash

logger = logging.getLogger("lecturenotes.transcribe")


async def transcribe_audio(
    wav_path: Path,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    job: Optional[Any] = None,
) -> Tuple[List[TranscriptSegment], str, str]:
    """Transcribe a WAV file using faster-whisper on CPU with int8 quantization.

    Uses compound caching (audio SHA-256 + whisper model name + language).
    Immediately unloads model from RAM upon completion.

    Returns:
        (segments, detected_language, file_hash)
    """
    settings = get_settings()
    logger.info(f"Computing hash for caching: {wav_path.name}")
    file_hash = compute_file_hash(wav_path)
    
    # Check compound cache
    cache = TranscriptCache()
    cached = cache.get(file_hash, whisper_model=settings.WHISPER_MODEL)
    if cached:
        logger.info(f"Reusing cached transcription for {file_hash[:12]}...")
        if progress_callback:
            progress_callback(100.0, "Transcribing audio (Cached)")
        segments = [TranscriptSegment(**seg) for seg in cached.get("segments", [])]
        language = cached.get("language", "en")
        return segments, language, file_hash

    # Run transcription in a worker thread
    loop = asyncio.get_event_loop()
    
    def _check_cancelled() -> bool:
        if job and getattr(job, "stage", None):
            from backend.models import JobStage
            return job.stage == JobStage.CANCELLED
        return False

    segments, language = await loop.run_in_executor(
        None,
        _transcribe_worker,
        str(wav_path),
        progress_callback,
        _check_cancelled,
    )

    # Save to compound cache
    cache.set(
        file_hash=file_hash,
        transcript_data={
            "language": language,
            "segments": [seg.model_dump() for seg in segments],
        },
        whisper_model=settings.WHISPER_MODEL,
        language=language,
    )

    return segments, language, file_hash


def _transcribe_worker(
    wav_path: str,
    progress_callback: Optional[Callable[[float, str], None]],
    check_cancelled: Optional[Callable[[], bool]] = None,
) -> Tuple[List[TranscriptSegment], str]:
    """Synchronously load Whisper model, transcribe with VAD, and immediately free model from memory."""
    from faster_whisper import WhisperModel

    settings = get_settings()
    logger.info(
        f"Loading Whisper model '{settings.WHISPER_MODEL}' (device={settings.WHISPER_DEVICE}, "
        f"compute_type={settings.WHISPER_COMPUTE_TYPE}, cpu_threads={settings.WHISPER_THREADS})..."
    )
    
    model = WhisperModel(
        settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
        cpu_threads=settings.WHISPER_THREADS,
    )

    try:
        segments_iter, info = model.transcribe(
            wav_path,
            beam_size=5,
            language=None,  # Auto-detect language
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        language = info.language
        total_duration = max(0.1, info.duration)
        logger.info(f"Detected language: {language} (duration: {total_duration:.1f}s)")

        segments: List[TranscriptSegment] = []
        for seg in segments_iter:
            if check_cancelled and check_cancelled():
                logger.info("Transcription worker detected cancellation. Aborting early.")
                raise asyncio.CancelledError("Transcription cancelled by user.")

            segments.append(
                TranscriptSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                )
            )
            # Update progress based on timestamp vs total duration
            if progress_callback and total_duration > 0:
                pct = min(99.0, (seg.end / total_duration) * 100.0)
                progress_callback(pct, f"Transcribing audio ({pct:.0f}%)")

        if not segments:
            raise ValueError("No speech detected in audio. The file may be silent or noisy.")

        if progress_callback:
            progress_callback(100.0, "Transcription complete")

        return segments, language

    finally:
        # Memory reclamation: immediately delete model and trigger garbage collection
        logger.info("Freeing Whisper model from RAM (del model + gc.collect)...")
        try:
            del model
        except Exception:
            pass
        gc.collect()
        logger.info("Whisper model unloaded from RAM.")
