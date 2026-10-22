"""Pydantic models for API request/response and internal pipeline data structures.

templates/sample_lecture.json serves as the strict canonical data contract.
All pipeline components (structure.py, questions.py, pdf_builder.py) validate
against these models.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class JobStage(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    CLEANING = "cleaning"
    STRUCTURING = "structuring_notes"
    GENERATING_QUESTIONS = "generating_questions"
    BUILDING_PDF = "building_pdf"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class DetailLevel(str, Enum):
    CONCISE = "concise"
    DETAILED = "detailed"


class Difficulty(str, Enum):
    EASY = "Easy"
    MODERATE = "Moderate"
    HARD = "Hard"


class QuestionType(str, Enum):
    THEORY = "Theory"
    NUMERICAL = "Numerical"


class ThemeName(str, Enum):
    INDIGO = "indigo"
    EMERALD = "emerald"
    SUNSET = "sunset"
    PRINT_FRIENDLY = "print-friendly"


class AIEngine(str, Enum):
    GEMINI = "gemini"
    OLLAMA = "ollama"


# ── Canonical Study Book Data Contract (Matches sample_lecture.json) ───────────

class CalloutItem(BaseModel):
    """Optional callout box within a concept."""
    type: str = "tip"  # tip, warning, important, note
    title: str = "Note"
    text: str


class ConceptDefinitionItem(BaseModel):
    """Part 1: Concept & Definition card."""
    id: str
    title: str
    definition: Optional[str] = None
    explanation: str
    key_points: List[str] = Field(default_factory=list)
    latex: Optional[str] = None
    callout: Optional[CalloutItem] = None


class ExampleItem(BaseModel):
    """Part 2: Worked conceptual example."""
    id: str
    title: str
    context: str
    steps: List[str] = Field(default_factory=list)
    takeaway: Optional[str] = None


class NumericalStepItem(BaseModel):
    """Individual calculation step in a numerical problem."""
    step_num: int
    title: str
    description: str
    math: Optional[str] = None


class NumericalItem(BaseModel):
    """Part 3: Numerical calculation problem card."""
    id: str
    title: str
    is_long: Optional[bool] = False
    problem: str
    given: Dict[str, str] = Field(default_factory=dict)
    find: str
    formulas_used: List[str] = Field(default_factory=list)
    solution_steps: List[NumericalStepItem] = Field(default_factory=list)
    final_answer: str


class FormulaItem(BaseModel):
    """Part 4: Formula cheat-sheet row."""
    name: str
    latex: str
    description: str
    units: Optional[str] = None


class QuestionItem(BaseModel):
    """Part 5: Tiered examination question with solution in answer key."""
    id: str
    number: int
    difficulty: str = "Easy"  # Easy, Moderate, Hard
    type: str = "Theory"      # Theory, Numerical
    question: str
    answer: str


class LectureBook(BaseModel):
    """Canonical Study Book data representation (Strict 1-to-1 match with sample_lecture.json)."""
    title: str
    subject: str
    summary: str
    source: Optional[str] = "Lecture Recording"
    date: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%B %d, %Y"))
    duration_str: Optional[str] = "45 minutes"
    theme: Optional[str] = "indigo"
    is_demo: Optional[bool] = False
    concepts_and_definitions: List[ConceptDefinitionItem] = Field(default_factory=list)
    examples: List[ExampleItem] = Field(default_factory=list)
    numericals: List[NumericalItem] = Field(default_factory=list)
    formula_sheet: List[FormulaItem] = Field(default_factory=list)
    questions: List[QuestionItem] = Field(default_factory=list)


# Alias for backward compatibility
LectureBookData = LectureBook


# ── Intermediate Pipeline Models ───────────────────────────────────────────────

class StructuredNotesOutput(BaseModel):
    """Output contract produced by LLM structuring phase (structure.py)."""
    title: str
    subject: str
    summary: str
    concepts_and_definitions: List[ConceptDefinitionItem] = Field(default_factory=list)
    examples: List[ExampleItem] = Field(default_factory=list)
    numericals: List[NumericalItem] = Field(default_factory=list)
    formula_sheet: List[FormulaItem] = Field(default_factory=list)


class QuestionsOutput(BaseModel):
    """Output contract produced by LLM question generation phase (questions.py)."""
    questions: List[QuestionItem] = Field(default_factory=list)


# ── API Models ─────────────────────────────────────────────────────────────────

class JobSettings(BaseModel):
    """Configuration settings for processing a job."""
    ai_engine: AIEngine = AIEngine.GEMINI
    theme: ThemeName = ThemeName.INDIGO
    fast_mode: bool = True
    detail_level: DetailLevel = DetailLevel.DETAILED
    question_count: int = Field(default=12, ge=3, le=30)
    title: Optional[str] = None
    subject: Optional[str] = None
    lecture_type: Optional[str] = "auto"  # auto, stem, conceptual
    whisper_model: Optional[str] = "small"  # tiny, base, small, medium


class JobCreateRequest(BaseModel):
    """Request body for creating a new job from a video link."""
    url: Optional[str] = None
    ai_engine: AIEngine = AIEngine.GEMINI
    theme: ThemeName = ThemeName.INDIGO
    fast_mode: bool = True
    detail_level: DetailLevel = DetailLevel.DETAILED
    question_count: int = Field(default=12, ge=3, le=30)
    title: Optional[str] = None
    subject: Optional[str] = None
    lecture_type: Optional[str] = "auto"
    whisper_model: Optional[str] = "small"


class JobStatusResponse(BaseModel):
    """Response for job status queries."""
    job_id: str
    status: JobStage
    stage_label: str = ""
    progress: int = 0  # 0-100
    current_chunk: int = 0
    total_chunks: int = 0
    error: Optional[str] = None
    title: Optional[str] = None
    duration_seconds: Optional[int] = None
    word_count: Optional[int] = None
    section_count: Optional[int] = None
    concept_count: Optional[int] = None
    example_count: Optional[int] = None
    numerical_count: Optional[int] = None
    formula_count: Optional[int] = None
    question_count: Optional[int] = None
    created_at: str = ""
    pdf_ready: bool = False
    transcript_ready: bool = False
    is_demo: bool = False
    can_resume: bool = False
    ai_engine: str = "gemini"
    theme: str = "indigo"


class TranscriptSegment(BaseModel):
    """A timestamped segment of transcription."""
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    """Full transcript retrieval model."""
    job_id: str
    language: str = "en"
    raw_text: str = ""
    cleaned_text: str = ""
    segments: List[TranscriptSegment] = Field(default_factory=list)
