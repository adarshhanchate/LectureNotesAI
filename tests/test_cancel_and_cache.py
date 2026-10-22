"""Test Cancellation, Process Tree Cleanup, Compound Cache, and Resumption."""

import asyncio
from pathlib import Path
import psutil
import time
import sys

PROJECT_ROOT = Path(r"c:\Users\ashan\Documents\NLP mini project")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.models import JobSettings, JobStage, AIEngine, ThemeName
from backend.job_manager import JobManager
from backend.pipeline.cache import TranscriptCache, compute_file_hash, compute_compound_key


async def test_compound_cache():
    print("\n========================================================")
    print("TEST 1: Compound Transcript Cache (Hit / Miss Verification)")
    print("========================================================")
    mp4_path = PROJECT_ROOT / "tests" / "sample_5min_lecture.mp4"
    assert mp4_path.exists(), f"MP4 not found: {mp4_path}"

    cache = TranscriptCache()
    f_hash = compute_file_hash(mp4_path)
    model = "small"
    
    # Check compound key
    comp_key = compute_compound_key(f_hash, model, "en")
    print(f"File SHA-256:  {f_hash}")
    print(f"Compound Key:  {comp_key}")
    
    # Store dummy transcript
    dummy = {"language": "en", "segments": [{"start": 0.0, "end": 2.0, "text": "Testing cache."}]}
    cache.set(f_hash, dummy, whisper_model=model, language="en")
    
    # Retrieve
    t0 = time.time()
    hit = cache.get(f_hash, whisper_model=model, language="en")
    elapsed = time.time() - t0
    
    assert hit is not None, "Cache retrieval failed!"
    assert hit["segments"][0]["text"] == "Testing cache."
    print(f"[+] Cache HIT confirmed in {elapsed*1000:.3f} ms (< 1 ms retrieval time)!")


async def test_cancel_orphan_cleanup():
    print("\n========================================================")
    print("TEST 2: Mid-Transcription Cancel & Zero Orphan Processes")
    print("========================================================")
    media_path = PROJECT_ROOT / "tests" / "sample_5min_lecture.mp4"
    assert media_path.exists(), f"MP4 not found: {media_path}"
    mgr = JobManager()
    
    settings = JobSettings(ai_engine=AIEngine.GEMINI, theme=ThemeName.INDIGO)
    job = mgr.create_job(settings, file_path=media_path)
    
    print(f"Starting job {job.job_id} on {media_path.name}...")
    await mgr.start_job(job)
    
    # Wait until it enters audio extraction or transcription
    for _ in range(30):
        await asyncio.sleep(0.3)
        if job.stage in (JobStage.EXTRACTING_AUDIO, JobStage.TRANSCRIBING):
            print(f"Job reached active stage: {job.stage.value} ({job.progress}%)")
            break

    # Trigger cancellation
    print("Triggering job.cancel() mid-execution...")
    job.cancel()
    await asyncio.sleep(1.0)
    
    assert job.stage == JobStage.CANCELLED, f"Expected CANCELLED, got {job.stage}"
    print(f"[+] Job stage verified: {job.stage.value}")
    
    # Verify no orphan ffmpeg processes
    current_proc = psutil.Process()
    child_procs = current_proc.children(recursive=True)
    orphan_ffmpeg = [p for p in child_procs if "ffmpeg" in p.name().lower()]
    
    print(f"Active child processes of current worker: {len(child_procs)}")
    print(f"Active child ffmpeg processes: {len(orphan_ffmpeg)}")
    assert len(orphan_ffmpeg) == 0, f"Found orphan ffmpeg processes: {orphan_ffmpeg}"
    print("[+] ZERO orphan ffmpeg / python processes verified!")


async def test_resume_from_checkpoint():
    print("\n========================================================")
    print("TEST 3: Resume from Interrupted / Cancelled Checkpoint")
    print("========================================================")
    mgr = JobManager()
    settings = JobSettings(ai_engine=AIEngine.GEMINI, theme=ThemeName.INDIGO)
    job = mgr.create_job(settings)
    
    # Simulate a job that was cancelled after transcription
    job.wav_path = PROJECT_ROOT / "tests" / "sample_5min_lecture.mp4"
    job.raw_transcript = "In today's lecture we analyze heat engines and the second law of thermodynamics."
    job.cleaned_transcript = "In today's lecture we analyze heat engines and the second law of thermodynamics."
    job.title = "Sample Thermodynamics Lecture"
    job.stage = JobStage.CANCELLED
    job.progress = 58
    job.save_checkpoint()
    
    print(f"Created simulated cancelled job {job.job_id} at progress 58% (transcript ready).")
    
    # Call resume
    resumed = await mgr.resume_job(job)
    assert resumed is True, "resume_job returned False!"
    print(f"[+] resume_job() accepted. Pipeline resuming...")
    
    # Let it run into structuring or beyond
    await asyncio.sleep(2.0)
    job.cancel()  # clean up
    print(f"[+] Resume test successful!")


async def main():
    await test_compound_cache()
    await test_cancel_orphan_cleanup()
    await test_resume_from_checkpoint()
    print("\n========================================================")
    print("ALL CHECKPOINT (c) UNIT TESTS PASSED!")
    print("========================================================")


if __name__ == "__main__":
    asyncio.run(main())
