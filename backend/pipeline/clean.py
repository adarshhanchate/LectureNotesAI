"""Transcript cleaning and chunking module — removes fillers, normalizes punctuation, and chunks at ~1,500 words."""

from __future__ import annotations
import re
import logging
from typing import List

logger = logging.getLogger("lecturenotes.clean")

# Common filler words/phrases to remove
FILLERS = [
    r"\b(um+|uh+|er+|ah+|eh+|hmm+|huh|like,?\s+you know|you know|I mean|sort of|kind of|basically|actually|literally|right\?)\b",
]

# Repeated word pattern (e.g., "the the", "is is")
REPEATED_WORDS = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)


def clean_transcript(text: str) -> str:
    """Clean a raw transcript:
    - Remove filler words
    - Remove repeated words
    - Fix spacing and punctuation
    - Preserve technical terms and formulas
    """
    if not text or not text.strip():
        return text

    logger.info(f"Cleaning transcript ({len(text.split())} words)")
    cleaned = text

    # Remove filler words
    for pattern in FILLERS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove repeated words (keep one)
    cleaned = REPEATED_WORDS.sub(r"\1", cleaned)

    # Fix multiple spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    # Fix space before punctuation
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)

    # Ensure space after punctuation
    cleaned = re.sub(r"([.,;:!?])([A-Za-z])", r"\1 \2", cleaned)

    # Fix sentence capitalization after periods
    def capitalize_after_period(match):
        return match.group(1) + match.group(2).upper()

    cleaned = re.sub(r"(\.\s+)([a-z])", capitalize_after_period, cleaned)

    # Remove empty parentheses or brackets
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*\]", "", cleaned)

    # Clean up leading/trailing whitespace
    cleaned = cleaned.strip()

    # Capitalize first character
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    word_count_after = len(cleaned.split())
    logger.info(f"Cleaned transcript: {word_count_after} words")
    return cleaned


def chunk_transcript(text: str, max_words: int = 1500) -> List[str]:
    """Split transcript into coherent chunks of roughly max_words (default: ~1,500 words), splitting at sentence boundaries when possible."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_words = 0

    for para in paragraphs:
        # Split paragraph into sentences
        sentences = re.split(r"(?<=[.!?])\s+", para)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            words = len(sentence.split())
            if current_words + words > max_words and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_words = words
            else:
                current_chunk.append(sentence)
                current_words += words

    if current_chunk:
        if chunks and current_words < 250:
            chunks[-1] += " " + " ".join(current_chunk)
        else:
            chunks.append(" ".join(current_chunk))

    logger.info(f"Chunked transcript into {len(chunks)} chunks (~{max_words} words each)")
    return chunks
