"""Audio extraction module — converts media to 16kHz mono WAV using ffmpeg or native WAV handling."""

from __future__ import annotations
import asyncio
import logging
import shutil
import wave
from pathlib import Path
from typing import Optional, Any
from backend.utils import run_cancellable_subprocess

logger = logging.getLogger("lecturenotes.audio")

# Search paths for ffmpeg on Windows
_FFMPEG_CANDIDATES = [
    "ffmpeg",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]


def _find_ffmpeg() -> str:
    """Find available ffmpeg binary."""
    for candidate in _FFMPEG_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate

    # Search WinGet packages directory if present
    import os
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        winget_pkgs = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for p in winget_pkgs.glob("**/ffmpeg.exe"):
                return str(p)

    return "ffmpeg"


async def extract_audio(input_path: Path, job_dir: Path, job: Optional[Any] = None) -> Path:
    """Convert any audio or video file to 16kHz mono WAV for transcription.
    
    If the file is already a valid WAV, reads and validates it natively using the standard wave module.
    """
    output_path = job_dir / "audio.wav"
    ffmpeg_bin = _find_ffmpeg()

    # Native WAV handling: If already WAV, inspect header
    if input_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(input_path), "rb") as wf:
                channels = wf.getnchannels()
                rate = wf.getframerate()
                logger.info(f"Input is already a WAV file: {channels} channel(s), {rate} Hz")
                if channels == 1 and rate == 16000:
                    shutil.copyfile(input_path, output_path)
                    return output_path
                elif not shutil.which(ffmpeg_bin):
                    # If ffmpeg is missing but it's a WAV, copy directly so Whisper can read it
                    logger.warning("ffmpeg not in PATH; using original WAV file directly.")
                    shutil.copyfile(input_path, output_path)
                    return output_path
        except Exception as e:
            logger.debug(f"Native WAV check exception: {e}")

    # Use ffmpeg for transcoding
    cmd = [
        ffmpeg_bin,
        "-i", str(input_path),
        "-vn",                   # Disable video stream
        "-acodec", "pcm_s16le",  # 16-bit PCM audio
        "-ar", "16000",          # 16kHz sample rate
        "-ac", "1",              # 1 channel (mono)
        "-y",                    # Overwrite output
        str(output_path),
    ]

    logger.info(f"Extracting audio using {ffmpeg_bin} from: {input_path.name}")
    try:
        returncode, stdout, stderr = await run_cancellable_subprocess(cmd, cwd=job_dir, job=job)
        if returncode != 0:
            err = stderr.decode(errors="replace").strip()
            raise RuntimeError(f"FFmpeg extraction failed: {err[:400]}")
    except FileNotFoundError:
        # If input is audio, fallback to direct copy if possible
        if input_path.suffix.lower() in (".wav", ".mp3", ".m4a"):
            logger.warning("ffmpeg binary not found in PATH; copying source directly for Whisper.")
            shutil.copyfile(input_path, output_path)
            return output_path
        raise RuntimeError("ffmpeg is required to extract audio from video files. Please install ffmpeg.")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Audio extraction produced an empty file.")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Audio extracted successfully: {size_mb:.2f} MB WAV")
    return output_path


async def get_audio_duration(wav_path: Path) -> float:
    """Get duration of a WAV file in seconds using native wave module or ffprobe."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames) / float(rate)
    except Exception:
        pass

    # Fallback to ffprobe
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(wav_path),
        ]
        returncode, stdout, stderr = await run_cancellable_subprocess(cmd)
        if returncode == 0 and stdout:
            return float(stdout.decode().strip())
        return 0.0
    except Exception:
        return 0.0
