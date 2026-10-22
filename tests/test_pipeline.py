"""End-to-end benchmark and verification test suite for LectureNotes AI.

Tests the full pipeline on tests/sample_5min_lecture.wav, records
timings per stage, and audits the generated PDF content and question tags.

Usage:
    python -m tests.test_pipeline [--engine ollama|gemini] [--theme indigo|emerald|sunset|print-friendly]
"""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from backend.config import get_settings
from backend.models import (
    JobSettings,
    AIEngine,
    ThemeName,
    DetailLevel,
)
from backend.job_manager import job_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_pipeline")


async def run_test(engine: str = "ollama", theme: str = "indigo") -> dict:
    settings = get_settings()
    sample_wav = settings.PROJECT_ROOT / "tests" / "sample_5min_lecture.wav"
    
    if not sample_wav.exists():
        raise FileNotFoundError(f"Sample lecture audio not found at {sample_wav}")

    print("=" * 65)
    print(f"   LectureNotes AI -- End-to-End Test & Benchmark ({engine.upper()})")
    print("=" * 65)
    print(f"Audio Input:  {sample_wav.name} ({sample_wav.stat().st_size / (1024*1024):.2f} MB)")
    print(f"AI Engine:    {engine}")
    print(f"Theme:        {theme}")
    print("-" * 65)

    job_settings = JobSettings(
        ai_engine=AIEngine(engine),
        theme=ThemeName(theme),
        fast_mode=True,
        detail_level=DetailLevel.DETAILED,
        question_count=6,
    )

    job = job_manager.create_job(job_settings, file_path=sample_wav)
    print(f"Job ID: {job.job_id}")

    timings = {}
    t_start = time.time()

    # Run the pipeline
    await job_manager.run_pipeline(job)
    total_time = time.time() - t_start

    print("-" * 65)
    print(f"Pipeline finished with status: {job.stage.value.upper()}")
    if job.error:
        print(f"[-] Pipeline error: {job.error}")
        return {"status": "failed", "error": job.error}

    # ── Content Audits ────────────────────────────────────────────────────────
    print("\n[Auditing Generated Study Book Content]")
    
    # 1. Numericals audit
    numericals = job.structured_data.get("numericals", []) if job.structured_data else []
    print(f"  Numericals Found: {len(numericals)}")
    for idx, num in enumerate(numericals):
        title = num.title if hasattr(num, "title") else num.get("title")
        final_ans = num.final_answer if hasattr(num, "final_answer") else num.get("final_answer")
        print(f"    [{idx + 1}] {title} -> Final Answer: {final_ans[:40]}...")

    # 2. Questions audit (Verify every single question has Theory or Numerical tag)
    questions = job.questions_data or []
    print(f"  Questions Generated: {len(questions)}")
    all_tagged = True
    tag_counts = {"Theory": 0, "Numerical": 0}
    for idx, q in enumerate(questions):
        cat = q.get("category", "") if isinstance(q, dict) else q.category.value
        diff = q.get("difficulty", "") if isinstance(q, dict) else q.difficulty.value
        q_text = q.get("question", "") if isinstance(q, dict) else q.question
        if cat in tag_counts:
            tag_counts[cat] += 1
        else:
            all_tagged = False
        print(f"    [{idx + 1}] [{diff}] [{cat}] {q_text[:50]}...")

    print(f"  Question Tags Distribution: {tag_counts}")
    assert len(questions) > 0, "No questions were generated!"
    assert all_tagged, "Not all questions have valid Theory/Numerical tags!"
    print("  \u2714\ufe0f All questions have verified (Theory/Numerical) category tags.")

    # 3. PDF File verification
    pdf_path = job.pdf_path
    assert pdf_path and pdf_path.exists(), "PDF output file does not exist!"
    pdf_size_kb = pdf_path.stat().st_size / 1024
    print(f"  \u2714\ufe0f PDF generated at: {pdf_path}")
    print(f"  \u2714\ufe0f PDF Size: {pdf_size_kb:.1f} KB")

    print("\n" + "=" * 65)
    print(f"Total Execution Time: {total_time:.2f} seconds")
    print("=" * 65)

    return {
        "status": "success",
        "job_id": job.job_id,
        "pdf_path": str(pdf_path),
        "total_time_seconds": round(total_time, 2),
        "numericals_count": len(numericals),
        "questions_count": len(questions),
        "tag_counts": tag_counts,
        "word_count": job.word_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Run full pipeline test and benchmark.")
    parser.add_argument("--engine", choices=["ollama", "gemini"], default="ollama")
    parser.add_argument("--theme", choices=["indigo", "emerald", "sunset", "print-friendly"], default="indigo")
    args = parser.parse_args()

    res = asyncio.run(run_test(engine=args.engine, theme=args.theme))
    if res.get("status") != "success":
        exit(1)


if __name__ == "__main__":
    main()
