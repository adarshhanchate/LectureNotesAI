"""LLM-based note structuring module — converts transcripts into canonical lecture books.

Strictly adheres to templates/sample_lecture.json data contract.
Enforces simple LaTeX formatting rules (\frac, \sqrt, subscripts, superscripts,
Greek letters, \mathrm{}; strictly no \text, \dfrac, align, or matrices).
"""

from __future__ import annotations
import logging
from typing import Optional, Callable, Dict, Any, List

from backend.llm import get_llm_provider
from backend.models import (
    JobSettings,
    ConceptDefinitionItem,
    ExampleItem,
    NumericalItem,
    NumericalStepItem,
    FormulaItem,
    CalloutItem,
    StructuredNotesOutput,
)
from backend.pipeline.clean import chunk_transcript

logger = logging.getLogger("lecturenotes.structure")

STRUCTURE_SYSTEM_PROMPT = """You are an elite academic professor and STEM textbook author.
Your task is to transform raw lecture transcript text into a rigorous, beautiful study book chapter.

Output strictly valid JSON matching this schema:
{
  "title": "Clear, authoritative academic chapter title",
  "subject": "Academic discipline / subject area",
  "summary": "Concise 3-5 sentence synthesis of the fundamental principles and practical outcomes",
  "concepts_and_definitions": [
    {
      "id": "concept-1",
      "title": "Exact Title of Concept or Topic",
      "definition": "Formal rigorous scientific or mathematical definition",
      "explanation": "In-depth theoretical explanation and physical intuition",
      "key_points": [
        "Core key point 1",
        "Core key point 2"
      ],
      "latex": "Primary governing formula in LaTeX (or null if purely qualitative)",
      "callout": {
        "type": "tip" | "warning" | "important",
        "title": "Callout Box Heading",
        "text": "Practical takeaway, exam pitfall, or application tip"
      }
    }
  ],
  "examples": [
    {
      "id": "ex-1",
      "title": "Descriptive title of worked conceptual scenario",
      "context": "Physical scenario description with initial conditions and parameters",
      "steps": [
        "Step 1: First logical deduction",
        "Step 2: Second analytical progression"
      ],
      "takeaway": "Key theoretical conclusion"
    }
  ],
  "numericals": [
    {
      "id": "num-1",
      "title": "Descriptive problem title",
      "is_long": false,
      "problem": "Complete problem statement with explicit numerical values and units",
      "given": {
        "Initial Parameter (P_1)": "100 kPa",
        "Temperature (T_1)": "300 K"
      },
      "find": "Exact quantities to compute (with symbols)",
      "formulas_used": [
        "\\frac{P_1 V_1}{T_1} = \\frac{P_2 V_2}{T_2}"
      ],
      "solution_steps": [
        {
          "step_num": 1,
          "title": "Identify Knowns & Convert Units",
          "description": "Convert all quantities to standard SI units.",
          "math": "T_1 = 27 + 273.15 = 300.15 \\mathrm{K}"
        }
      ],
      "final_answer": "Complete final boxed result with units"
    }
  ],
  "formula_sheet": [
    {
      "name": "Law or Relationship Name",
      "latex": "Formula in simple LaTeX without $$ wrappers (e.g. \\Delta U = Q - W)",
      "description": "Physical meaning of variables",
      "units": "Units (e.g. Joules [J], Pascals [Pa])"
    }
  ]
}

CRITICAL MATHEMATICAL FORMATTING RULES:
1. Use SIMPLE LaTeX ONLY: \\frac, \\sqrt, subscripts (_), superscripts (^), Greek letters (\\alpha, \\beta, \\Delta, etc.), and \\mathrm{} for text subscripts.
2. STRICTLY FORBIDDEN: Do NOT use \\text{...}, \\dfrac, \\tfrac, align environments, or matrix commands. Use \\mathrm{...} instead of \\text{...}. Use \\frac instead of \\dfrac.
3. Every numerical problem MUST have given, find, formulas_used, solution_steps, and a final_answer.
4. If the lecture did not explicitly work a numerical problem, construct 1 relevant engineering/analytical calculation from the lecture formulas.
5. Return ONLY strictly valid JSON.
"""


async def structure_notes(
    transcript: str,
    job_settings: JobSettings,
    title_hint: str = "Lecture Notes",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """Structure the full transcript into canonical study book sections."""
    engine_name = getattr(job_settings, "ai_engine", "gemini")
    if hasattr(engine_name, "value"):
        engine_name = engine_name.value

    provider = get_llm_provider(
        engine_name,
        fast_mode=getattr(job_settings, "fast_mode", True),
    )
    chunks = chunk_transcript(transcript, max_words=1500)
    total_chunks = len(chunks)

    all_concepts: List[ConceptDefinitionItem] = []
    all_examples: List[ExampleItem] = []
    all_numericals: List[NumericalItem] = []
    all_formulas: List[FormulaItem] = []
    summaries: List[str] = []
    chapter_title = title_hint
    subject = "STEM & Applied Sciences"

    for idx, chunk in enumerate(chunks):
        logger.info(f"Structuring chunk {idx + 1}/{total_chunks} with {provider.model_name}...")
        if progress_callback:
            progress_callback(idx + 1, total_chunks, f"Structuring notes (chunk {idx + 1}/{total_chunks})")

        prompt = f"""Lecture Title Context: {title_hint}
Chunk {idx + 1} of {total_chunks}:
----------------------------------------
{chunk}
----------------------------------------
Convert this lecture chunk into structured study book content as specified."""

        data = await provider.generate_json(prompt, system_prompt=STRUCTURE_SYSTEM_PROMPT)

        if data.get("title") and chapter_title in ("Lecture Notes", "Untitled Lecture", "Lecture Recording"):
            chapter_title = data.get("title")
        if data.get("subject"):
            subject = data.get("subject")
        if data.get("summary"):
            summaries.append(data.get("summary"))

        # Ingest Concepts
        for c in data.get("concepts_and_definitions", []):
            if isinstance(c, dict) and c.get("title"):
                cid = f"concept-{len(all_concepts) + 1}"
                callout = None
                if c.get("callout") and isinstance(c["callout"], dict):
                    callout = CalloutItem(
                        type=c["callout"].get("type", "tip"),
                        title=c["callout"].get("title", "Key Tip"),
                        text=c["callout"].get("text", ""),
                    )
                all_concepts.append(
                    ConceptDefinitionItem(
                        id=cid,
                        title=c.get("title", f"Topic {len(all_concepts) + 1}"),
                        definition=c.get("definition"),
                        explanation=c.get("explanation", ""),
                        key_points=c.get("key_points", []),
                        latex=c.get("latex"),
                        callout=callout,
                    )
                )

        # Ingest Examples
        for ex in data.get("examples", []):
            if isinstance(ex, dict) and ex.get("title"):
                all_examples.append(
                    ExampleItem(
                        id=f"ex-{len(all_examples) + 1}",
                        title=ex.get("title", f"Example {len(all_examples) + 1}"),
                        context=ex.get("context", ""),
                        steps=ex.get("steps", []),
                        takeaway=ex.get("takeaway"),
                    )
                )

        # Ingest Numericals
        for num in data.get("numericals", []):
            if isinstance(num, dict) and num.get("problem"):
                steps: List[NumericalStepItem] = []
                for s_i, st in enumerate(num.get("solution_steps", [])):
                    if isinstance(st, dict):
                        steps.append(
                            NumericalStepItem(
                                step_num=st.get("step_num", s_i + 1),
                                title=st.get("title", f"Step {s_i + 1}"),
                                description=st.get("description", ""),
                                math=st.get("math"),
                            )
                        )
                all_numericals.append(
                    NumericalItem(
                        id=f"num-{len(all_numericals) + 1}",
                        title=num.get("title", f"Numerical Problem {len(all_numericals) + 1}"),
                        is_long=bool(len(steps) > 4 or num.get("is_long")),
                        problem=num.get("problem", ""),
                        given=num.get("given", {}),
                        find=num.get("find", ""),
                        formulas_used=num.get("formulas_used", []),
                        solution_steps=steps,
                        final_answer=num.get("final_answer", ""),
                    )
                )

        # Ingest Formulas
        for f in data.get("formula_sheet", []):
            if isinstance(f, dict) and f.get("name") and f.get("latex"):
                all_formulas.append(
                    FormulaItem(
                        name=f.get("name", "Formula"),
                        latex=f.get("latex", ""),
                        description=f.get("description", ""),
                        units=f.get("units"),
                    )
                )

    # De-duplicate formulas by name/latex
    unique_formulas: List[FormulaItem] = []
    seen_f = set()
    for f in all_formulas:
        k = (f.name.lower(), f.latex.strip())
        if k not in seen_f:
            seen_f.add(k)
            unique_formulas.append(f)

    final_summary = " ".join(summaries) if summaries else "Summary of the lecture contents."
    is_demo = getattr(provider, "is_demo", False)

    out = {
        "title": chapter_title,
        "subject": subject,
        "summary": final_summary,
        "concepts_and_definitions": all_concepts,
        "examples": all_examples,
        "numericals": all_numericals,
        "formula_sheet": unique_formulas,
        "is_demo": is_demo,
    }

    # Validate output contract
    StructuredNotesOutput.model_validate(out)
    return out
