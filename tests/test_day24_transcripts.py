import pytest

from screening_ai.transcript_processor import clean_transcript
from screening_ai.transcript_normalizer import normalize_turn
from screening_ai.stt_service import STTResult, STTSegment

def test_removes_fillers_and_fixes_spacing():
    assert clean_transcript("um, i mean I built  a model") == "I built a model."

def test_preserves_original_text_in_normalized_turn():
    raw = "uh i worked on APIs"
    turn = normalize_turn(raw, sequence_no=1, language="en-IN")
    assert turn["text"] == raw
    assert turn["normalized_text"] == "I worked on APIs."
    assert turn["sequence_no"] == 1

@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"interrupted": True}, "interrupted"),
        ({"partial": True}, "partial"),
        ({"silence_detected": True}, "silence"),
    ],
)
def test_turn_completion_states(flags, expected):
    turn = normalize_turn("I was working", sequence_no=2, **flags)
    assert turn["completion_status"] == expected

def test_empty_speech_is_silence():
    turn = normalize_turn("  ", sequence_no=3)
    assert turn["silence_detected"] is True
    assert turn["completion_status"] == "silence"

def test_confidence_range_validation():
    with pytest.raises(ValueError):
        normalize_turn("hello", sequence_no=1, confidence_score=1.2)

def test_stt_result_serialization():
    result = STTResult(
        text="Hello",
        language="en",
        segments=[STTSegment("Hello", 0.0, 0.8)],
        silence_detected=False,
    )
    payload = result.to_dict()
    assert payload["segments"][0]["end"] == 0.8
    assert payload["confidence_score"] is None
