"""Adapters connecting Day 24 STT/transcript components to Day 25."""
from __future__ import annotations
from typing import Any, Dict, Optional
from screening_ai.transcript_normalizer import normalize_turn

class Day24TranscriptAdapter:
    @staticmethod
    def from_stt_result(stt_result: Any, *, question: str = "", question_id: Optional[str] = None,
                        sequence_no: int = 1, speaker: str = "candidate",
                        interrupted: bool = False, partial: bool = False) -> Dict[str, Any]:
        if hasattr(stt_result, "to_dict") and callable(stt_result.to_dict):
            stt_result = stt_result.to_dict()
        if not isinstance(stt_result, dict):
            raise TypeError("stt_result must be a dict or expose to_dict()")
        raw_text = stt_result.get("text", "")
        if not isinstance(raw_text, str):
            raise TypeError("STT result 'text' must be a string")
        turn = normalize_turn(raw_text, sequence_no=sequence_no, speaker=speaker,
            language=stt_result.get("language"), confidence_score=stt_result.get("confidence_score"),
            interrupted=interrupted, partial=partial,
            silence_detected=bool(stt_result.get("silence_detected", False)), question_id=question_id)
        turn["segments"] = stt_result.get("segments", [])
        turn["stt_source"] = "day24_stt_provider"
        payload = Day24TranscriptAdapter.from_normalized_turn(turn, question=question)
        payload["transcript_metadata"]["source"] = "day24_stt_result"
        return payload

    @staticmethod
    def from_normalized_turn(turn: Dict[str, Any], *, question: str = "") -> Dict[str, Any]:
        if not isinstance(turn, dict):
            raise TypeError("turn must be a dictionary")
        answer = turn.get("normalized_text") or turn.get("text") or ""
        if not isinstance(answer, str):
            raise TypeError("turn text must be a string")
        fields = ("turn_id", "sequence_no", "speaker", "question_id", "language", "timestamp",
                  "confidence_score", "confidence_source", "completion_status", "text", "segments", "stt_source")
        metadata = {key: turn.get(key) for key in fields}
        metadata.update({"source": "day24_normalized_turn",
            "interrupted": bool(turn.get("interrupted", False)),
            "partial": bool(turn.get("partial", False)),
            "silence_detected": bool(turn.get("silence_detected", False))})
        return {"answer": answer, "question": question, "transcript_metadata": metadata}
