# Day 25 – Answer Intent & Understanding Engine

## Implementation
- Rule-based intent classification, entity extraction, off-topic detection and answer validation.
- Optional semantic intent classification using `sentence-transformers/all-MiniLM-L6-v2`.
- Direct integration with the supplied Day 24 `STTResult`, `clean_transcript()` and `normalize_turn()` implementations.

## Day 24 integration
The package contains the supplied Day 24 modules under `screening_ai/`: `stt_service.py`,
`transcript_processor.py`, and `transcript_normalizer.py`. `understand_stt_result()` accepts
an `STTResult` dataclass or dict. It invokes the actual `normalize_turn()`, which calls the
actual `clean_transcript()`. `understand_turn()` accepts normalized turn dictionaries.
Verbatim transcript text and normalized text remain separately available in metadata.

Example:
```python
from intent_engine import AnswerUnderstandingEngine
from screening_ai.stt_service import STTResult, STTSegment
stt = STTResult(text="uh I have two years of Python experience", language="en-IN",
    segments=[STTSegment("uh I have two years of Python experience", 0.0, 2.8)])
result = AnswerUnderstandingEngine().understand_stt_result(
    stt, "How much experience do you have?", question_id="q_exp")
```


## Real Audio Integration Testing

### Test Environment
- Speech-to-text provider: Faster-Whisper
- Model: small
- Device: CPU
- Language: English
- Pipeline: Audio → Day 24 STT → Transcript Normalization → Day 25 Answer Understanding

### Test Results

| Audio file | STT result | Intent result | Answer status |
|---|---|---|---|
| candidate_answer.wav | Success | Skills, Experience | Incomplete |
| short_answer.wav | Success | Skills | Complete |
| unclear_answer.wav | Success | Skills, Experience | Incomplete |

### Observations

1. The system successfully transcribed all three real audio recordings.
2. The candidate project explanation produced Python and Machine Learning entities.
3. The short response correctly identified Python as a skill.
4. The unclear response was transcribed despite hesitation and filler words.
5. The engine generated follow-up questions when experience duration was missing.
6. All three recordings completed processing without runtime errors.

### Limitations Identified

- Semantic classification was disabled during this test.
- The current output does not expose normalized_text for independent verification of filler removal.
- STT confidence scores were unavailable in these results.

### Overall Result

Real audio integration: PASS (3/3 files processed successfully).

This validates the real-audio transcription and Day 24–Day 25 integration path. Full project regression testing and independent transcript-cleaning verification remain pending.

### Evidence

Output file: reports/DAY25_REAL_AUDIO_TEST_OUTPUT.json

## Semantic mode
Install `requirements-day25-semantic.txt`; enable with `AnswerUnderstandingEngine(semantic=True)`.
Similarity scores are not calibrated probabilities or hiring scores. Entity extraction remains rule-based.

## Tests
Run `python -m pytest tests/test_day24_transcripts.py tests/test_day25_intent_engine.py tests/test_day25_day24_end_to_end.py -v`.
The included tests cover the supplied Day 24 transcript tests, Day 25 tests, and direct adapter integration.

## Limitations
- Semantic examples and thresholds require validation on a representative labeled dataset.
- Entity extraction remains rule-based and English-centric.
- FasterWhisperProvider requires the optional `faster-whisper` dependency and an audio file.
- The supplied Day 24 source modules are integrated; full application/API/database wiring and actual audio-file end-to-end testing remain outside this package.
