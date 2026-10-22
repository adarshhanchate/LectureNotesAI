"""In-process Job Manager with state persistence, cancel, and resume capabilities."""

from __future__ import annotations
import asyncio
import json
import logging
import shutil
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List

from backend.config import get_settings
from backend.models import (
    JobStage,
    JobStatusResponse,
    JobSettings,
    TranscriptSegment,
    TranscriptResponse,
)
from backend.llm.base import SetupRequiredError, DailyQuotaExhaustedError, RateLimitExceededError

logger = logging.getLogger("lecturenotes.jobs")


class Job:
    """Represents a single lecture-to-notes processing job with checkpointing."""

    def __init__(
        self,
        job_id: str,
        job_settings: JobSettings,
        url: Optional[str] = None,
        file_path: Optional[Path] = None,
    ):
        settings = get_settings()
        self.job_id = job_id
        self.settings = job_settings
        self.url = url
        self.file_path = file_path
        self.stage = JobStage.QUEUED
        self.stage_label: str = "Waiting in queue..."
        self.progress = 0
        self.current_chunk = 0
        self.total_chunks = 0
        self.error: Optional[str] = None
        self.created_at = datetime.now()
        self.is_demo = False

        # Metadata & intermediate data
        self.title = "Untitled Lecture"
        self.source = url or ("Uploaded File" if file_path else "Direct Lecture")
        self.duration_seconds = 0
        self.word_count = 0
        self.language = "en"
        self.file_hash: Optional[str] = None

        # Checkpoints & Data
        self.segments: List[TranscriptSegment] = []
        self.raw_transcript: str = ""
        self.cleaned_transcript: str = ""
        self.structured_data: Optional[Dict[str, Any]] = None
        self.questions_data: Optional[List[Dict[str, Any]]] = None

        # Paths
        self.job_dir = settings.JOBS_DIR / job_id
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.job_dir / "checkpoint.json"
        self.audio_path: Optional[Path] = None
        self.wav_path: Optional[Path] = None
        self.pdf_path: Optional[Path] = None
        self.transcript_path: Optional[Path] = None

        # Async Task handle & child process tracking for safe Windows cancellation
        self._async_task: Optional[asyncio.Task] = None
        self._child_pids: set[int] = set()

    def register_pid(self, pid: int):
        """Track active child process PID."""
        self._child_pids.add(pid)

    def unregister_pid(self, pid: int):
        """Untrack completed child process PID."""
        self._child_pids.discard(pid)

    def update_stage(self, stage: JobStage, progress: int = 0, label: Optional[str] = None):
        """Update job stage, progress, and stage label."""
        self.stage = stage
        self.progress = max(0, min(100, progress))
        if label:
            self.stage_label = label
        logger.info(f"Job {self.job_id}: {stage.value} ({self.progress}%) - {self.stage_label}")
        self.save_checkpoint()

    def update_chunk_progress(self, current_chunk: int, total_chunks: int, label: str):
        """Update granular chunk-level progress for LLM structuring."""
        self.current_chunk = current_chunk
        self.total_chunks = total_chunks
        self.stage_label = label
        # Interpolate between 55% and 80% for structuring
        pct = 55 + int((current_chunk / max(1, total_chunks)) * 25)
        self.progress = max(self.progress, pct)
        logger.info(f"Job {self.job_id}: Chunk {current_chunk}/{total_chunks} ({self.progress}%)")
        self.save_checkpoint()

    def fail(self, error: str):
        """Mark job as failed."""
        self.stage = JobStage.FAILED
        self.error = error
        self.stage_label = f"Failed: {error}"
        logger.error(f"Job {self.job_id} FAILED: {error}")
        self.save_checkpoint()

    def cancel(self):
        """Cancel active processing task and terminate all child processes (ffmpeg/yt-dlp)."""
        from backend.utils import kill_process_tree
        for pid in list(self._child_pids):
            kill_process_tree(pid)
        self._child_pids.clear()

        if self._async_task and not self._async_task.done():
            self._async_task.cancel()
        self.stage = JobStage.CANCELLED
        self.stage_label = "Job cancelled by user"
        logger.info(f"Job {self.job_id} CANCELLED by user.")
        self.save_checkpoint()

    def save_checkpoint(self):
        """Persist current job state to disk for resumption."""
        state = {
            "job_id": self.job_id,
            "stage": self.stage.value,
            "stage_label": self.stage_label,
            "progress": self.progress,
            "current_chunk": self.current_chunk,
            "total_chunks": self.total_chunks,
            "title": self.title,
            "source": self.source,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "language": self.language,
            "file_hash": self.file_hash,
            "is_demo": self.is_demo,
            "error": self.error,
            "wav_path": str(self.wav_path) if self.wav_path else None,
            "pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "has_raw_transcript": bool(self.raw_transcript),
            "has_cleaned_transcript": bool(self.cleaned_transcript),
            "has_structured_data": bool(self.structured_data),
            "has_questions": bool(self.questions_data),
        }
        try:
            with open(self.checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

            if self.structured_data or self.questions_data:
                payload = {
                    "structured_data": {
                        "title": self.structured_data.get("title") if self.structured_data else "",
                        "subject": self.structured_data.get("subject") if self.structured_data else "",
                        "summary": self.structured_data.get("summary") if self.structured_data else "",
                        "concepts_and_definitions": [
                            c.model_dump() if hasattr(c, "model_dump") else c
                            for c in (self.structured_data.get("concepts_and_definitions", []) if self.structured_data else [])
                        ],
                        "examples": [
                            e.model_dump() if hasattr(e, "model_dump") else e
                            for e in (self.structured_data.get("examples", []) if self.structured_data else [])
                        ],
                        "numericals": [
                            n.model_dump() if hasattr(n, "model_dump") else n
                            for n in (self.structured_data.get("numericals", []) if self.structured_data else [])
                        ],
                        "formula_sheet": [
                            f.model_dump() if hasattr(f, "model_dump") else f
                            for f in (self.structured_data.get("formula_sheet", []) if self.structured_data else [])
                        ],
                    } if self.structured_data else None,
                    "questions_data": self.questions_data,
                }
                payload_path = self.job_dir / "checkpoint_payload.json"
                with open(payload_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save checkpoint for {self.job_id}: {e}")

    def to_status(self) -> JobStatusResponse:
        """Convert to API response."""
        stage_labels = {
            JobStage.QUEUED: "Waiting in queue...",
            JobStage.DOWNLOADING: "Downloading lecture audio...",
            JobStage.EXTRACTING_AUDIO: "Extracting 16kHz audio...",
            JobStage.TRANSCRIBING: "Transcribing with Whisper (CPU int8)...",
            JobStage.CLEANING: "Cleaning transcript & chunking...",
            JobStage.STRUCTURING: "Structuring notes with AI...",
            JobStage.GENERATING_QUESTIONS: "Generating categorized exam questions...",
            JobStage.BUILDING_PDF: "Rendering math formulas & compiling PDF...",
            JobStage.COMPLETED: "Done! Your study book is ready.",
            JobStage.CANCELLED: "Job cancelled by user.",
            JobStage.FAILED: f"Error: {self.error or 'Pipeline error'}",
        }
        label = self.stage_label or stage_labels.get(self.stage, "")
        can_resume = self.stage in (JobStage.CANCELLED, JobStage.FAILED) and bool(
            self.wav_path or self.cleaned_transcript or self.structured_data
        )

        concept_count = len(self.structured_data.get("concepts_and_definitions", [])) if self.structured_data else None
        example_count = len(self.structured_data.get("examples", [])) if self.structured_data else None
        numerical_count = len(self.structured_data.get("numericals", [])) if self.structured_data else None
        formula_count = len(self.structured_data.get("formula_sheet", [])) if self.structured_data else None
        question_count = len(self.questions_data) if self.questions_data else None
        section_count = concept_count or 0

        engine_name = self.settings.ai_engine.value if hasattr(self.settings.ai_engine, "value") else str(self.settings.ai_engine)
        theme_name = self.settings.theme.value if hasattr(self.settings.theme, "value") else str(self.settings.theme)

        return JobStatusResponse(
            job_id=self.job_id,
            status=self.stage,
            stage_label=label,
            progress=self.progress,
            current_chunk=self.current_chunk,
            total_chunks=self.total_chunks,
            error=self.error,
            title=self.title,
            duration_seconds=self.duration_seconds,
            word_count=self.word_count,
            section_count=section_count,
            concept_count=concept_count,
            example_count=example_count,
            numerical_count=numerical_count,
            formula_count=formula_count,
            question_count=question_count,
            created_at=self.created_at.isoformat(),
            pdf_ready=bool(self.pdf_path and self.pdf_path.exists()),
            transcript_ready=bool(self.cleaned_transcript or (self.transcript_path and self.transcript_path.exists())),
            is_demo=self.is_demo,
            can_resume=can_resume,
            ai_engine=engine_name,
            theme=theme_name,
        )

    def get_transcript_response(self) -> TranscriptResponse:
        """Return full transcript data with segments."""
        return TranscriptResponse(
            job_id=self.job_id,
            language=self.language,
            raw_text=self.raw_transcript,
            cleaned_text=self.cleaned_transcript,
            segments=self.segments,
        )

    def cleanup(self):
        """Remove job files."""
        try:
            if self.job_dir.exists():
                shutil.rmtree(self.job_dir)
                logger.info(f"Cleaned up job directory: {self.job_id}")
        except Exception as e:
            logger.warning(f"Cleanup failed for {self.job_id}: {e}")


class JobManager:
    """Manages processing jobs and execution state."""

    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()

    def create_job(
        self,
        job_settings: JobSettings,
        url: Optional[str] = None,
        file_path: Optional[Path] = None,
    ) -> Job:
        """Create a new job and return it."""
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id, job_settings, url=url, file_path=file_path)
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[Job]:
        """Return all tracked jobs sorted newest first."""
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    async def start_job(self, job: Job):
        """Launch background pipeline execution."""
        task = asyncio.create_task(self.run_pipeline(job))
        job._async_task = task

    async def resume_job(self, job: Job) -> bool:
        """Resume an interrupted or cancelled job from last saved checkpoint."""
        if job.stage not in (JobStage.CANCELLED, JobStage.FAILED):
            return False
        
        # Restore checkpoint payload if available
        payload_path = job.job_dir / "checkpoint_payload.json"
        if payload_path.exists():
            try:
                with open(payload_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    if payload.get("structured_data") and not job.structured_data:
                        job.structured_data = payload["structured_data"]
                    if payload.get("questions_data") and not job.questions_data:
                        job.questions_data = payload["questions_data"]
            except Exception as e:
                logger.warning(f"Error restoring checkpoint payload: {e}")

        job.error = None
        job.update_stage(JobStage.QUEUED, job.progress, "Resuming pipeline...")
        await self.start_job(job)
        return True

    async def run_pipeline(self, job: Job):
        """Execute full end-to-end pipeline with checkpoints and memory isolation."""
        from backend.pipeline.download import download_media
        from backend.pipeline.audio import extract_audio
        from backend.pipeline.transcribe import transcribe_audio
        from backend.pipeline.clean import clean_transcript
        from backend.pipeline.structure import structure_notes
        from backend.pipeline.questions import generate_questions
        from backend.pipeline.pdf_builder import build_pdf

        try:
            # Stage 1: Download / File Input
            if not job.audio_path:
                job.update_stage(JobStage.DOWNLOADING, 5, "Downloading lecture media...")
                if job.url:
                    audio_path, meta = await download_media(job.url, job.job_dir, job=job)
                    job.audio_path = audio_path
                    job.title = meta.get("title", job.title)
                    job.duration_seconds = meta.get("duration", 0)
                elif job.file_path:
                    job.audio_path = job.file_path
                    job.title = job.file_path.stem.replace("_", " ").replace("-", " ").title()
                job.update_stage(JobStage.DOWNLOADING, 15, "Media ready")

            # Stage 2: Audio Conversion to 16kHz WAV
            if not job.wav_path or not job.wav_path.exists():
                job.update_stage(JobStage.EXTRACTING_AUDIO, 20, "Extracting 16kHz mono WAV audio...")
                job.wav_path = await extract_audio(job.audio_path, job.job_dir, job=job)
                job.update_stage(JobStage.EXTRACTING_AUDIO, 30, "Audio extraction complete")

            # Stage 3: Whisper Transcription (CPU int8 with memory isolation)
            if not job.raw_transcript:
                job.update_stage(JobStage.TRANSCRIBING, 35, "Transcribing speech with Whisper (CPU int8)...")

                def _whisper_progress(pct: float, msg: str):
                    scaled = 35 + int(pct * 0.20)
                    job.update_stage(JobStage.TRANSCRIBING, scaled, msg)

                segments, language, file_hash = await transcribe_audio(
                    job.wav_path,
                    progress_callback=_whisper_progress,
                    job=job,
                )
                job.segments = segments
                job.language = language
                job.file_hash = file_hash
                job.raw_transcript = " ".join(seg.text for seg in segments)
                job.word_count = len(job.raw_transcript.split())
                job.update_stage(JobStage.TRANSCRIBING, 55, "Transcription complete")

            # Stage 4: Cleaning Transcript
            if not job.cleaned_transcript:
                job.update_stage(JobStage.CLEANING, 56, "Cleaning filler words & standardizing text...")
                job.cleaned_transcript = clean_transcript(job.raw_transcript)
                job.transcript_path = job.job_dir / "transcript.txt"
                job.transcript_path.write_text(job.cleaned_transcript, encoding="utf-8")
                job.update_stage(JobStage.CLEANING, 58, "Transcript cleaned & chunked")

            # Stage 5: Structuring Notes with AI
            if not job.structured_data:
                job.update_stage(JobStage.STRUCTURING, 60, "Structuring lecture notes with AI...")

                def _chunk_cb(curr: int, tot: int, msg: str):
                    job.update_chunk_progress(curr, tot, msg)

                hint = job.settings.title or job.settings.subject or job.title
                structured_res = await structure_notes(
                    transcript=job.cleaned_transcript,
                    job_settings=job.settings,
                    title_hint=hint,
                    progress_callback=_chunk_cb,
                )
                job.structured_data = structured_res
                if structured_res.get("title") and job.title in ("Untitled Lecture", "Uploaded Lecture"):
                    job.title = structured_res.get("title")
                if structured_res.get("is_demo"):
                    job.is_demo = True
                job.update_stage(JobStage.STRUCTURING, 80, "Structuring complete")

            # Stage 6: Question Bank Generation
            if not job.questions_data:
                job.update_stage(JobStage.GENERATING_QUESTIONS, 82, "Generating exam questions & answer key...")
                questions_res = await generate_questions(
                    transcript=job.cleaned_transcript,
                    structured_content=job.structured_data,
                    job_settings=job.settings,
                )
                job.questions_data = [q.model_dump() for q in questions_res]
                job.update_stage(JobStage.GENERATING_QUESTIONS, 90, "Question bank generated")

            # Stage 7: PDF Rendering with WeasyPrint & matplotlib.mathtext
            job.update_stage(JobStage.BUILDING_PDF, 92, "Rendering math SVGs & compiling PDF...")
            pdf_out = job.job_dir / f"{job.job_id}_notes.pdf"

            book_dict = {
                "title": job.title,
                "subject": job.structured_data.get("subject", "STEM & General Studies"),
                "summary": job.structured_data.get("summary", ""),
                "source": job.source,
                "date": datetime.now().strftime("%B %d, %Y"),
                "duration_str": f"{job.duration_seconds // 60} minutes" if job.duration_seconds else "45 minutes",
                "concepts_and_definitions": [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in job.structured_data.get("concepts_and_definitions", [])
                ],
                "examples": [
                    e.model_dump() if hasattr(e, "model_dump") else e
                    for e in job.structured_data.get("examples", [])
                ],
                "numericals": [
                    n.model_dump() if hasattr(n, "model_dump") else n
                    for n in job.structured_data.get("numericals", [])
                ],
                "formula_sheet": [
                    f.model_dump() if hasattr(f, "model_dump") else f
                    for f in job.structured_data.get("formula_sheet", [])
                ],
                "questions": job.questions_data,
                "is_demo": job.is_demo,
            }

            theme_name = job.settings.theme.value if hasattr(job.settings.theme, "value") else str(job.settings.theme)
            job.pdf_path = build_pdf(book_dict, pdf_out, theme=theme_name)
            job.update_stage(JobStage.COMPLETED, 100, "Done! Your study book is ready.")
            logger.info(f"Job {job.job_id} pipeline completed successfully.")
            logger.info(f"Job {job.job_id} pipeline completed successfully.")

        except asyncio.CancelledError:
            logger.info(f"Pipeline task for job {job.job_id} was cancelled.")
            job.cancel()
        except SetupRequiredError as e:
            logger.warning(f"Setup required for job {job.job_id}: {e}")
            job.fail(str(e))
        except DailyQuotaExhaustedError as e:
            logger.error(f"Quota exhausted for job {job.job_id}: {e}")
            job.fail(str(e))
        except RateLimitExceededError as e:
            logger.error(f"Rate limit exceeded for job {job.job_id}: {e}")
            job.fail(str(e))
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Pipeline error for job {job.job_id}:\n{tb}")
            job.fail(f"{type(e).__name__}: {str(e)}")

    async def cleanup_old_jobs(self):
        """Remove jobs older than CLEANUP_AFTER_HOURS."""
        settings = get_settings()
        now = datetime.now()
        to_remove = []
        for job_id, job in self.jobs.items():
            age_hours = (now - job.created_at).total_seconds() / 3600
            if age_hours > settings.CLEANUP_AFTER_HOURS:
                job.cleanup()
                to_remove.append(job_id)
        for jid in to_remove:
            del self.jobs[jid]


# Global manager instance
job_manager = JobManager()
