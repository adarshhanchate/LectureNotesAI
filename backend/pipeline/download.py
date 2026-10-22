"""Download module — uses yt-dlp to download media from URLs."""
from __future__ import annotations
import asyncio
import logging
import json
from pathlib import Path
from typing import Tuple, Optional, Any
from backend.utils import run_cancellable_subprocess

logger = logging.getLogger("lecturenotes.download")


async def download_media(url: str, job_dir: Path, job: Optional[Any] = None) -> Tuple[Path, dict]:
    """
    Download best audio from a URL using yt-dlp.
    Returns (audio_file_path, metadata_dict).
    """
    output_template = str(job_dir / "source.%(ext)s")
    info_file = job_dir / "info.json"

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestaudio/best",
        "-o", output_template,
        "--write-info-json",
        "--no-write-playlist-metafiles",
        "--restrict-filenames",
        "--no-overwrites",
        url,
    ]

    logger.info(f"Downloading from: {url}")
    returncode, stdout, stderr = await run_cancellable_subprocess(cmd, cwd=job_dir, job=job)

    if returncode != 0:
        error_msg = stderr.decode(errors="replace").strip()
        # Check common errors
        if "Private video" in error_msg or "Sign in" in error_msg:
            raise ValueError("This video is private or requires sign-in. Please use a public video.")
        elif "not available" in error_msg or "unavailable" in error_msg:
            raise ValueError("This video is unavailable. Please check the URL.")
        elif "Unsupported URL" in error_msg:
            raise ValueError("Unsupported URL format. Please provide a valid video link.")
        else:
            raise RuntimeError(f"Download failed: {error_msg[:500]}")

    # Find the downloaded file
    downloaded_files = list(job_dir.glob("source.*"))
    # Exclude .json files
    downloaded_files = [f for f in downloaded_files if f.suffix != ".json"]
    if not downloaded_files:
        raise FileNotFoundError("Download completed but no media file was found.")

    audio_path = downloaded_files[0]
    logger.info(f"Downloaded: {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Parse metadata
    metadata = {"title": "Untitled Lecture", "duration": 0}
    info_files = list(job_dir.glob("*.info.json"))
    if info_files:
        try:
            with open(info_files[0], "r", encoding="utf-8") as f:
                info = json.load(f)
            metadata["title"] = info.get("title", "Untitled Lecture")
            metadata["duration"] = int(info.get("duration", 0))
            metadata["uploader"] = info.get("uploader", "")
            metadata["upload_date"] = info.get("upload_date", "")
        except Exception as e:
            logger.warning(f"Could not parse info.json: {e}")

    return audio_path, metadata
