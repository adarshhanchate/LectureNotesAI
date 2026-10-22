"""Run Full Pipeline on sample_5min_lecture.mp4 for both Gemini and Ollama (qwen2.5:3b).

Measures per-stage timings, generates PDFs, and creates high-res screenshots
of:
1. Index page
2. A numerical page
3. The questions page
for both runs.
"""

from __future__ import annotations
import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import time
import fitz

PROJECT_ROOT = Path(r"c:\Users\ashan\Documents\NLP mini project")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.models import JobSettings, AIEngine, ThemeName, JobStage
from backend.job_manager import JobManager
from backend.pipeline.audio import extract_audio
from backend.pipeline.transcribe import transcribe_audio
from backend.pipeline.clean import clean_transcript
from backend.pipeline.structure import structure_notes
from backend.pipeline.questions import generate_questions
from backend.pipeline.pdf_builder import build_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_pipeline_e2e")

SCREENSHOTS_DIR = Path(r"C:\Users\ashan\.gemini\antigravity-ide\brain\0957641c-3107-49a3-a864-67d3c6aeeee4\screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


async def run_single_pipeline(
    engine: AIEngine,
    fast_mode: bool = True,
    theme: ThemeName = ThemeName.INDIGO,
) -> tuple[dict[str, float], Path]:
    settings = get_settings()
    mp4_path = PROJECT_ROOT / "tests" / "sample_5min_lecture.mp4"
    assert mp4_path.exists(), f"MP4 not found: {mp4_path}"
    media_path = mp4_path
    
    run_dir = settings.TEMP_DIR / f"run_{engine.value}_{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    timings: dict[str, float] = {}
    
    print(f"\n=================================================================")
    print(f"RUNNING PIPELINE WITH ENGINE: {engine.value.upper()} (fast_mode={fast_mode})")
    print(f"=================================================================")
    
    # Stage 1: Audio Extraction
    t0 = time.time()
    print(f"Stage 1: Extracting 16kHz audio from {media_path.name}...")
    wav_path = await extract_audio(media_path, run_dir)
    timings["Audio Extraction"] = time.time() - t0
    print(f"  [+] Audio extracted in {timings['Audio Extraction']:.2f}s -> {wav_path.name}")
    
    # Stage 2: Faster-Whisper Transcription (Compound Cache Test)
    t0 = time.time()
    print("Stage 2: Transcribing audio with Faster-Whisper (CPU int8)...")
    segments, language, f_hash = await transcribe_audio(wav_path)
    timings["Transcription (STT)"] = time.time() - t0
    raw_text = " ".join(seg.text for seg in segments)
    print(f"  [+] Transcription in {timings['Transcription (STT)']:.2f}s | Words: {len(raw_text.split())} | Lang: {language}")
    
    # Stage 3: Cleaning & Normalization
    t0 = time.time()
    print("Stage 3: Cleaning transcript text...")
    cleaned_text = clean_transcript(raw_text)
    timings["Transcript Cleaning"] = time.time() - t0
    print(f"  [+] Cleaned in {timings['Transcript Cleaning']:.2f}s")
    
    # Stage 4: LLM Structuring
    t0 = time.time()
    print(f"Stage 4: Structuring notes via {engine.value}...")
    job_settings = JobSettings(
        ai_engine=engine,
        theme=theme,
        fast_mode=fast_mode,
        question_count=12,
    )
    structured_data = await structure_notes(
        transcript=cleaned_text,
        job_settings=job_settings,
        title_hint="Wumpus World & Knowledge-Based Agents",
    )
    timings["LLM Structuring"] = time.time() - t0
    print(f"  [+] Structuring completed in {timings['LLM Structuring']:.2f}s")
    print(f"      Concepts: {len(structured_data.get('concepts_and_definitions', []))}")
    print(f"      Numericals: {len(structured_data.get('numericals', []))}")
    print(f"      Formulas: {len(structured_data.get('formula_sheet', []))}")
    
    # Stage 5: Question Generation
    t0 = time.time()
    print(f"Stage 5: Generating questions via {engine.value}...")
    questions = await generate_questions(
        transcript=cleaned_text,
        structured_content=structured_data,
        job_settings=job_settings,
    )
    timings["Question Generation"] = time.time() - t0
    print(f"  [+] Generated {len(questions)} questions in {timings['Question Generation']:.2f}s")
    
    # Stage 6: PDF Compilation
    t0 = time.time()
    print("Stage 6: Building PDF with WeasyPrint & matplotlib.mathtext...")
    pdf_path = run_dir / f"study_book_{engine.value}.pdf"
    
    book_dict = {
        "title": structured_data.get("title", "Wumpus World & Knowledge-Based Agents"),
        "subject": structured_data.get("subject", "Artificial Intelligence"),
        "summary": structured_data.get("summary", ""),
        "source": media_path.name,
        "date": datetime.now().strftime("%B %d, %Y"),
        "duration_str": "8 minutes",
        "concepts_and_definitions": [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in structured_data.get("concepts_and_definitions", [])
        ],
        "examples": [
            e.model_dump() if hasattr(e, "model_dump") else e
            for e in structured_data.get("examples", [])
        ],
        "numericals": [
            n.model_dump() if hasattr(n, "model_dump") else n
            for n in structured_data.get("numericals", [])
        ],
        "formula_sheet": [
            f.model_dump() if hasattr(f, "model_dump") else f
            for f in structured_data.get("formula_sheet", [])
        ],
        "questions": [q.model_dump() if hasattr(q, "model_dump") else q for q in questions],
        "is_demo": False,
    }
    
    build_pdf(book_dict, pdf_path, theme=theme.value)
    timings["PDF Generation"] = time.time() - t0
    timings["Total Pipeline"] = sum(timings.values())
    print(f"  [+] PDF compiled in {timings['PDF Generation']:.2f}s -> {pdf_path.name} ({pdf_path.stat().st_size/1024:.1f} KB)")
    print(f"  [+] TOTAL PIPELINE TIME: {timings['Total Pipeline']:.2f}s")
    
    return timings, pdf_path


def take_screenshots(pdf_path: Path, prefix: str):
    """Find and render index, numerical, and questions pages to PNG."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"\nAnalyzing {pdf_path.name} ({total_pages} pages) for screenshots...")
    
    index_page_idx = 1  # 0-indexed page 2
    numerical_page_idx = None
    questions_page_idx = None
    
    for i, page in enumerate(doc):
        text = page.get_text()
        if "Table of Contents" in text or "TABLE OF CONTENTS" in text.upper():
            index_page_idx = i
        if numerical_page_idx is None and i >= 2 and ("Numerical Problem" in text or "Problem 3." in text or "Given Data" in text or "GIVEN DATA" in text.upper()):
            numerical_page_idx = i
        if questions_page_idx is None and i >= 2 and ("Practice Questions" in text or "QUESTION BANK" in text.upper() or "Difficulty: Easy" in text or "Difficulty:" in text):
            questions_page_idx = i
            
    if numerical_page_idx is None:
        numerical_page_idx = min(3, total_pages - 1)
    if questions_page_idx is None:
        questions_page_idx = min(total_pages - 2, total_pages - 1)
        
    print(f"Detected screenshot pages:")
    print(f"  - Index Page: Page {index_page_idx + 1}")
    print(f"  - Numerical Page: Page {numerical_page_idx + 1}")
    print(f"  - Questions Page: Page {questions_page_idx + 1}")
    
    # Render and save
    dpi = 150
    p_idx = doc[index_page_idx].get_pixmap(dpi=dpi)
    idx_path = SCREENSHOTS_DIR / f"{prefix}_index_p{index_page_idx+1}.png"
    p_idx.save(str(idx_path))
    print(f"  Saved: {idx_path.name}")
    
    p_num = doc[numerical_page_idx].get_pixmap(dpi=dpi)
    num_path = SCREENSHOTS_DIR / f"{prefix}_numerical_p{numerical_page_idx+1}.png"
    p_num.save(str(num_path))
    print(f"  Saved: {num_path.name}")
    
    p_q = doc[questions_page_idx].get_pixmap(dpi=dpi)
    q_path = SCREENSHOTS_DIR / f"{prefix}_questions_p{questions_page_idx+1}.png"
    p_q.save(str(q_path))
    print(f"  Saved: {q_path.name}")
    
    return {
        "index": idx_path,
        "numerical": num_path,
        "questions": q_path,
    }


async def main():
    # 1. Run Gemini
    gemini_timings, gemini_pdf = await run_single_pipeline(
        engine=AIEngine.GEMINI,
        fast_mode=True,
        theme=ThemeName.INDIGO,
    )
    gemini_shots = take_screenshots(gemini_pdf, "gemini")
    
    # 2. Run Ollama (qwen2.5:7b)
    ollama_timings, ollama_pdf = await run_single_pipeline(
        engine=AIEngine.OLLAMA,
        fast_mode=False,
        theme=ThemeName.INDIGO,
    )
    ollama_shots = take_screenshots(ollama_pdf, "ollama")
    
    # Summary Report
    print("\n" + "="*70)
    print("           FULL PIPELINE TIMING REPORT (sample_5min_lecture.mp4)")
    print("="*70)
    print(f"{'Pipeline Stage':<28} | {'Gemini (Cloud)':<18} | {'Ollama qwen2.5:3b (Local)':<22}")
    print("-"*70)
    stages = [
        "Audio Extraction",
        "Transcription (STT)",
        "Transcript Cleaning",
        "LLM Structuring",
        "Question Generation",
        "PDF Generation",
        "Total Pipeline",
    ]
    for s in stages:
        g_t = gemini_timings.get(s, 0.0)
        o_t = ollama_timings.get(s, 0.0)
        print(f"{s:<28} | {g_t:>14.2f} s | {o_t:>18.2f} s")
    print("="*70)
    
    report = {
        "gemini": {
            "timings": gemini_timings,
            "pdf": str(gemini_pdf),
            "screenshots": {k: str(v) for k, v in gemini_shots.items()},
        },
        "ollama": {
            "timings": ollama_timings,
            "pdf": str(ollama_pdf),
            "screenshots": {k: str(v) for k, v in ollama_shots.items()},
        },
    }
    with open(PROJECT_ROOT / "tests" / "pipeline_timing_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to tests/pipeline_timing_report.json")


if __name__ == "__main__":
    asyncio.run(main())
