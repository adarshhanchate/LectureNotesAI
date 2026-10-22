"""Question bank generation module using configured LLM provider.

Adheres strictly to the canonical QuestionItem contract in templates/sample_lecture.json.
Enforces simple LaTeX formatting rules (\frac, \sqrt, subscripts, superscripts,
Greek letters, \mathrm{}; strictly no \text, \dfrac, align, or matrices).
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional

from backend.llm import get_llm_provider
from backend.models import (
    JobSettings,
    QuestionItem,
    QuestionsOutput,
)

logger = logging.getLogger("lecturenotes.questions")

QUESTION_SYSTEM_PROMPT = """You are a senior university examiner preparing an examination question bank.
Generate a rigorous set of exam questions based strictly on the lecture topics and formulas provided.

Return strictly valid JSON matching this schema:
{
  "questions": [
    {
      "id": "q-1",
      "number": 1,
      "difficulty": "Easy" | "Moderate" | "Hard",
      "type": "Theory" | "Numerical",
      "question": "Question text using simple LaTeX for all math (e.g. $F = m a$ or $\\Delta U = Q - W$)",
      "answer": "Complete, comprehensive solution or analytical explanation"
    }
  ]
}

CRITICAL RULES:
1. Every single question MUST have a 'type': either 'Theory' or 'Numerical'.
2. Numerical questions MUST require concrete calculation using values and formulas from the lecture and include full step-by-step arithmetic in the answer.
3. Theory questions MUST test conceptual clarity, definitions, or fundamental physical principles.
4. Distribute difficulty evenly across Easy, Moderate, and Hard tiers.
5. MATHEMATICAL FORMATTING: Use SIMPLE LaTeX ONLY (\\frac, \\sqrt, subscripts _, superscripts ^, Greek letters, \\mathrm{}).
   STRICTLY FORBIDDEN: Do NOT use \\text{...}, \\dfrac, \\tfrac, align, or matrices. Use \\mathrm{...} instead of \\text{...}.
6. Return ONLY strictly valid JSON.
"""


async def generate_questions(
    transcript: str,
    structured_content: Dict[str, Any],
    job_settings: JobSettings,
) -> List[QuestionItem]:
    """Generate categorized question bank using the configured LLM provider."""
    engine_name = getattr(job_settings, "ai_engine", "gemini")
    if hasattr(engine_name, "value"):
        engine_name = engine_name.value

    provider = get_llm_provider(
        engine_name,
        fast_mode=getattr(job_settings, "fast_mode", True),
    )
    target_count = getattr(job_settings, "question_count", 12)
    logger.info(f"Generating {target_count} questions via {provider.model_name}...")

    # Build concise context from structured content
    title = structured_content.get("title", "Lecture")
    formulas = [
        f"{getattr(f, 'name', '')}: ${getattr(f, 'latex', '')}$"
        for f in structured_content.get("formula_sheet", [])
    ]
    concepts = [
        getattr(c, "title", "") for c in structured_content.get("concepts_and_definitions", [])
    ]

    context = (
        f"Lecture Title: {title}\n"
        f"Key Formulas:\n" + ("\n".join(formulas[:15]) if formulas else "None specified") + "\n\n"
        f"Core Concepts Covered:\n" + ("\n".join(concepts[:10]) if concepts else "General Topics")
    )

    prompt = f"""Target Number of Questions: {target_count}
Lecture Context:
----------------------------------------
{context}
----------------------------------------

Generate {target_count} high-quality exam questions adhering strictly to the JSON schema.
Ensure BOTH Theory and Numerical questions are included across Easy, Moderate, and Hard tiers."""

    data = await provider.generate_json(prompt, system_prompt=QUESTION_SYSTEM_PROMPT)
    raw_questions = data.get("questions", [])

    results: List[QuestionItem] = []
    for i, q in enumerate(raw_questions):
        diff_str = str(q.get("difficulty", "Easy")).capitalize()
        type_str = str(q.get("type", "Theory")).capitalize()

        if diff_str not in ("Easy", "Moderate", "Hard"):
            diff_str = "Moderate"

        if type_str not in ("Theory", "Numerical"):
            type_str = "Theory"

        results.append(
            QuestionItem(
                id=f"q-{i + 1}",
                number=i + 1,
                difficulty=diff_str,
                type=type_str,
                question=q.get("question", ""),
                answer=q.get("answer", ""),
            )
        )

    # Validate output
    QuestionsOutput(questions=results)
    logger.info(f"Successfully generated {len(results)} categorized questions.")
    return results
