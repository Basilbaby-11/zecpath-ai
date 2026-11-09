"""Normalize transcript turns and retain interruption/partial/silence metadata."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .transcript_processor import clean_transcript

def normalize_turn(
    raw_text: str,
    *,
    sequence_no: int,
    speaker: str = "candidate",
    language: str | None = None,
    confidence_score: float | None = None,
    interrupted: bool = False,
    partial: bool = False,
    silence_detected: bool = False,
    timestamp: str | None = None,
    question_id: str | None = None,
) -> dict[str, Any]:
    """Create a Day-23-compatible turn while preserving verbatim ASR text."""
    if sequence_no < 1:
        raise ValueError("sequence_no must be a positive integer")
    if speaker not in {"candidate", "ai_agent", "system", "human_recruiter"}:
        raise ValueError("Unsupported speaker")
    if confidence_score is not None and not 0.0 <= confidence_score <= 1.0:
        raise ValueError("confidence_score must be between 0 and 1")
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    status = (
        "silence" if silence_detected or not raw_text.strip()
        else "interrupted" if interrupted
        else "partial" if partial
        else "complete"
    )
    return {
        "turn_id": str(uuid4()),
        "sequence_no": sequence_no,
        "speaker": speaker,
        "question_id": question_id,
        "text": raw_text,
        "normalized_text": clean_transcript(raw_text),
        "language": language,
        "timestamp": timestamp,
        "confidence_score": confidence_score,
        "confidence_source": "asr" if confidence_score is not None else None,
        "completion_status": status,
        "interrupted": interrupted,
        "partial": partial,
        "silence_detected": silence_detected or not raw_text.strip(),
    }
