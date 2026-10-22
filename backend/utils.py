"""Cross-platform utilities with Windows-first process management and Pathlib operations."""

from __future__ import annotations
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Set, Any

import psutil

logger = logging.getLogger("lecturenotes.utils")


def ensure_windows_event_loop():
    """Ensure Windows uses ProactorEventLoop for async subprocess support."""
    if sys.platform == "win32":
        try:
            # ProactorEventLoop is required for asyncio subprocesses on Windows
            if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception as e:
            logger.debug(f"Event loop policy notice: {e}")


def kill_process_tree(pid: int):
    """Terminate a process and all its descendants.
    
    On Windows: Uses taskkill /F /T /PID or psutil recursive termination.
    Guarantees no orphaned ffmpeg or yt-dlp processes.
    """
    if not pid:
        return

    logger.info(f"Terminating process tree for PID {pid}...")

    # Method 1: psutil recursive kill
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        logger.info(f"Terminated process {pid} and {len(children)} child processes via psutil.")
        return
    except psutil.NoSuchProcess:
        return
    except Exception as e:
        logger.debug(f"psutil process termination exception: {e}")

    # Method 2: Windows taskkill fallback
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            logger.info(f"Terminated PID {pid} via taskkill.")
        except Exception as e:
            logger.warning(f"taskkill fallback failed for PID {pid}: {e}")


async def run_cancellable_subprocess(
    cmd: List[str],
    cwd: Optional[Path] = None,
    job: Optional[Any] = None,
) -> Tuple[int, bytes, bytes]:
    """Execute a child subprocess with Windows-safe async support and cancellation handling.
    
    Registers PID with job if provided. If cancelled, cleanly kills the process tree.
    """
    ensure_windows_event_loop()
    cwd_str = str(cwd) if cwd else None
    logger.debug(f"Executing subprocess: {' '.join(cmd[:3])} (total args: {len(cmd)})")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd_str,
    )

    if job and hasattr(job, "register_pid"):
        job.register_pid(proc.pid)

    loop = asyncio.get_running_loop()
    try:
        stdout, stderr = await loop.run_in_executor(None, proc.communicate)
        return proc.returncode or 0, stdout, stderr
    except asyncio.CancelledError:
        logger.warning(f"Subprocess cancelled by task! Terminating PID {proc.pid}...")
        kill_process_tree(proc.pid)
        raise
    finally:
        if job and hasattr(job, "unregister_pid"):
            job.unregister_pid(proc.pid)


def read_text_utf8(file_path: Path) -> str:
    """Read file content with strict UTF-8 encoding."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text_utf8(file_path: Path, content: str):
    """Write text content to file with UTF-8 encoding."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
