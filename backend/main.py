"""FastAPI Main Application — LectureNotes AI Backend."""

from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.models import (
    JobCreateRequest,
    JobSettings,
    JobStatusResponse,
    TranscriptResponse,
    DetailLevel,
    ThemeName,
    AIEngine,
)
from backend.job_manager import job_manager

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lecturenotes.api")


# ── Periodic Cleanup Lifespan ─────────────────────────────────────────────────
async def periodic_cleanup():
    """Run job directory cleanup every hour."""
    while True:
        await asyncio.sleep(3600)
        try:
            await job_manager.cleanup_old_jobs()
        except Exception as e:
            logger.error(f"Periodic cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing background cleanup and diagnostic logging."""
    settings = get_settings()
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("🚀 LectureNotes AI Backend Server Started")
    logger.info(f"   Configured LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"   Gemini Model:           {settings.GEMINI_MODEL}")
    logger.info(f"   Ollama Model:           {settings.OLLAMA_MODEL}")
    logger.info(f"   Whisper STT:            {settings.WHISPER_MODEL} ({settings.WHISPER_DEVICE}, {settings.WHISPER_COMPUTE_TYPE})")
    logger.info(f"   Demo Mode:              {settings.DEMO_MODE}")
    yield
    cleanup_task.cancel()


# ── FastAPI Application ────────────────────────────────────────────────────────
app = FastAPI(
    title="LectureNotes AI",
    description="Lecture-to-Notes Converter — Structured Study Books & Question Banks",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health and environment status endpoint."""
    settings = get_settings()
    has_gemini_key = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your-gemini-api-key-here")
    return {
        "status": "ok",
        "service": "LectureNotes AI",
        "llm_provider": settings.LLM_PROVIDER,
        "gemini_configured": has_gemini_key,
        "gemini_model": settings.GEMINI_MODEL,
        "ollama_url": settings.OLLAMA_BASE_URL,
        "ollama_model": settings.OLLAMA_MODEL,
        "demo_mode": settings.DEMO_MODE,
        "whisper_model": settings.WHISPER_MODEL,
        "whisper_device": settings.WHISPER_DEVICE,
        "whisper_compute_type": settings.WHISPER_COMPUTE_TYPE,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
    }


from fastapi import Request

async def _create_job_from_link_internal(
    url: str,
    ai_engine: str = "gemini",
    theme: str = "indigo",
    fast_mode: bool = True,
    detail_level: str = "detailed",
    question_count: int = 12,
    title: Optional[str] = None,
    subject: Optional[str] = None,
    lecture_type: str = "auto",
    whisper_model: Optional[str] = "small",
):
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Please provide a valid URL starting with http:// or https://")

    try:
        engine_enum = AIEngine(ai_engine.lower())
    except ValueError:
        engine_enum = AIEngine.GEMINI

    try:
        theme_enum = ThemeName(theme.lower())
    except ValueError:
        theme_enum = ThemeName.INDIGO

    try:
        detail_enum = DetailLevel(detail_level.lower())
    except ValueError:
        detail_enum = DetailLevel.DETAILED

    job_settings = JobSettings(
        ai_engine=engine_enum,
        theme=theme_enum,
        fast_mode=fast_mode,
        detail_level=detail_enum,
        question_count=max(3, min(30, question_count)),
        title=title.strip() if title and title.strip() else None,
        subject=subject.strip() if subject and subject.strip() else None,
        lecture_type=lecture_type,
        whisper_model=whisper_model or "small",
    )

    job = job_manager.create_job(job_settings, url=url)
    if title and title.strip():
        job.title = title.strip()
    logger.info(f"Created job {job.job_id} for URL: {url} (Engine: {engine_enum.value}, Theme: {theme_enum.value})")
    await job_manager.start_job(job)
    return {"job_id": job.job_id, "status": "queued"}


async def _create_job_from_uploaded_file(
    file: UploadFile,
    ai_engine: str = "gemini",
    theme: str = "indigo",
    fast_mode: bool = True,
    detail_level: str = "detailed",
    question_count: int = 12,
    title: Optional[str] = None,
    subject: Optional[str] = None,
    lecture_type: str = "auto",
    whisper_model: Optional[str] = "small",
):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Supported types: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
        )

    try:
        engine_enum = AIEngine(ai_engine.lower())
    except ValueError:
        engine_enum = AIEngine.GEMINI

    try:
        theme_enum = ThemeName(theme.lower())
    except ValueError:
        theme_enum = ThemeName.INDIGO

    try:
        detail_enum = DetailLevel(detail_level.lower())
    except ValueError:
        detail_enum = DetailLevel.DETAILED

    job_settings = JobSettings(
        ai_engine=engine_enum,
        theme=theme_enum,
        fast_mode=fast_mode,
        detail_level=detail_enum,
        question_count=max(3, min(30, question_count)),
        title=title.strip() if title and title.strip() else None,
        subject=subject.strip() if subject and subject.strip() else None,
        lecture_type=lecture_type,
        whisper_model=whisper_model or "small",
    )

    job = job_manager.create_job(job_settings)
    upload_path = job.job_dir / f"upload{ext}"
    upload_path.write_bytes(content)
    job.file_path = upload_path
    if title and title.strip():
        job.title = title.strip()
    else:
        job.title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()

    logger.info(f"Created upload job {job.job_id}: {file.filename} ({len(content) / (1024 * 1024):.1f} MB)")
    await job_manager.start_job(job)
    return {"job_id": job.job_id, "status": "queued"}


@app.get("/api/jobs", response_model=List[JobStatusResponse])
async def list_jobs():
    """List all tracked jobs, sorted newest first."""
    jobs = job_manager.list_jobs()
    return [j.to_status() for j in jobs]


@app.post("/api/jobs")
async def create_job(request: Request):
    """Unified job creation endpoint: accepts EITHER a video URL OR an uploaded file."""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_obj = form.get("file")
        url = form.get("url")
        ai_engine = str(form.get("ai_engine", "gemini"))
        theme = str(form.get("theme", "indigo"))
        fast_mode = str(form.get("fast_mode", "true")).lower() == "true"
        detail_level = str(form.get("detail_level", "detailed"))
        title = form.get("title")
        subject = form.get("subject")
        lecture_type = str(form.get("lecture_type", "auto"))
        whisper_model = form.get("whisper_model")
        try:
            question_count = int(form.get("question_count", 12))
        except (ValueError, TypeError):
            question_count = 12

        if file_obj and hasattr(file_obj, "filename") and file_obj.filename:
            return await _create_job_from_uploaded_file(
                file=file_obj,
                ai_engine=ai_engine,
                theme=theme,
                fast_mode=fast_mode,
                detail_level=detail_level,
                question_count=question_count,
                title=str(title) if title else None,
                subject=str(subject) if subject else None,
                lecture_type=lecture_type,
                whisper_model=str(whisper_model) if whisper_model else "small",
            )
        elif url:
            return await _create_job_from_link_internal(
                url=str(url),
                ai_engine=ai_engine,
                theme=theme,
                fast_mode=fast_mode,
                detail_level=detail_level,
                question_count=question_count,
                title=str(title) if title else None,
                subject=str(subject) if subject else None,
                lecture_type=lecture_type,
                whisper_model=str(whisper_model) if whisper_model else "small",
            )
        else:
            raise HTTPException(status_code=400, detail="Must provide either 'url' or 'file' in request.")
    else:
        # JSON body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body.")

        url = body.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required.")

        return await _create_job_from_link_internal(
            url=str(url),
            ai_engine=body.get("ai_engine", "gemini"),
            theme=body.get("theme", "indigo"),
            fast_mode=body.get("fast_mode", True),
            detail_level=body.get("detail_level", "detailed"),
            question_count=body.get("question_count", 12),
            title=body.get("title"),
            subject=body.get("subject"),
            lecture_type=body.get("lecture_type", "auto"),
            whisper_model=body.get("whisper_model", "small"),
        )


@app.post("/api/jobs/upload")
async def create_job_from_upload(
    file: UploadFile = File(...),
    ai_engine: str = Form(default="gemini"),
    theme: str = Form(default="indigo"),
    fast_mode: bool = Form(default=True),
    detail_level: str = Form(default="detailed"),
    question_count: int = Form(default=12),
):
    """Direct upload endpoint (alias for POST /api/jobs with multipart)."""
    return await _create_job_from_uploaded_file(
        file=file,
        ai_engine=ai_engine,
        theme=theme,
        fast_mode=fast_mode,
        detail_level=detail_level,
        question_count=question_count,
    )


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the status, progress, stage, and error details of a job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_status()


@app.get("/api/jobs/{job_id}/transcript")
async def get_job_transcript(job_id: str, format: str = "json"):
    """Retrieve the timestamped and cleaned transcript of a job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if format == "text":
        if not job.transcript_path or not job.transcript_path.exists():
            if not job.cleaned_transcript:
                raise HTTPException(status_code=404, detail="Transcript not ready yet.")
            return JSONResponse(content={"text": job.cleaned_transcript})
        return FileResponse(
            path=str(job.transcript_path),
            media_type="text/plain",
            filename=f"{job.title[:40].replace(' ', '_')}_transcript.txt",
        )

    # Return structured JSON response with segments
    return job.get_transcript_response()


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Abort an active job and free resources."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.cancel()
    return {"job_id": job_id, "status": "cancelled", "message": "Job cancelled successfully."}


@app.post("/api/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a failed or cancelled job from the last saved stage/chunk."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    resumed = await job_manager.resume_job(job)
    if not resumed:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be resumed (must be in failed or cancelled state with saved checkpoint).",
        )

    return {"job_id": job_id, "status": "resumed", "message": "Pipeline resumed from checkpoint."}


@app.get("/api/jobs/{job_id}/pdf")
async def download_pdf(job_id: str):
    """Download the completed study book PDF."""
    if job_id.startswith("mock_"):
        mock_pdf = Path(__file__).resolve().parent.parent / "sample_book_indigo.pdf"
        if mock_pdf.exists():
            return FileResponse(path=str(mock_pdf), media_type="application/pdf", filename="Demo_Lecture_StudyBook.pdf")

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.pdf_path or not job.pdf_path.exists():
        raise HTTPException(status_code=404, detail="Study book PDF is not ready yet.")

    filename = f"{job.title[:50].replace(' ', '_')}_StudyBook.pdf"
    return FileResponse(
        path=str(job.pdf_path),
        media_type="application/pdf",
        filename=filename,
    )


@app.get("/api/jobs/{job_id}/download")
async def download_job_pdf_alias(job_id: str):
    """Alias for /api/jobs/{job_id}/pdf."""
    return await download_pdf(job_id)


@app.get("/api/jobs/{job_id}/preview")
async def preview_pdf(job_id: str):
    """View PDF directly in browser iframe or embed modal with inline Content-Disposition."""
    if job_id.startswith("mock_"):
        mock_pdf = Path(__file__).resolve().parent.parent / "sample_book_indigo.pdf"
        if mock_pdf.exists():
            return FileResponse(
                path=str(mock_pdf),
                media_type="application/pdf",
                headers={"Content-Disposition": 'inline; filename="Demo_Lecture_StudyBook.pdf"'},
            )

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.pdf_path or not job.pdf_path.exists():
        raise HTTPException(status_code=404, detail="Study book PDF is not ready yet.")

    filename = f"{job.title[:50].replace(' ', '_')}_StudyBook.pdf"
    return FileResponse(
        path=str(job.pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@app.get("/api/sample-file")
async def get_sample_file():
    """Serve sample_5min_lecture.mp4 for browser file upload testing."""
    sample_path = Path(__file__).resolve().parent.parent / "tests" / "sample_5min_lecture.mp4"
    if sample_path.exists():
        return FileResponse(
            path=str(sample_path),
            media_type="video/mp4",
            filename="sample_5min_lecture.mp4",
        )
    raise HTTPException(status_code=404, detail="Sample lecture file not found.")


# ── Frontend Static Files ─────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
