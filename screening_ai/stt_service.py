"""Speech-to-text provider adapter. faster-whisper is an optional dependency."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, Any

@dataclass
class STTSegment:
    text: str
    start: float
    end: float

@dataclass
class STTResult:
    text: str
    language: str | None
    segments: list[STTSegment]
    confidence_score: float | None = None
    silence_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "segments": [asdict(segment) for segment in self.segments],
            "confidence_score": self.confidence_score,
            "silence_detected": self.silence_detected,
        }

class STTProvider(Protocol):
    def transcribe(self, audio_path: str | Path, *,
                   language: str | None = None) -> STTResult: ...

class FasterWhisperProvider:
    """Local STT adapter; install faster-whisper separately to enable it."""

    def __init__(self, model_size: str = "small", device: str = "cpu",
                 compute_type: str = "int8") -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is optional. Install it with "
                "`pip install faster-whisper` to use this provider."
            ) from exc
        self._model = WhisperModel(
            model_size, device=device, compute_type=compute_type
        )

    def transcribe(self, audio_path: str | Path, *,
                   language: str | None = None) -> STTResult:
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        segments_iter, info = self._model.transcribe(
            str(path), language=language, vad_filter=True
        )
        segments = [
            STTSegment(text=segment.text.strip(), start=float(segment.start),
                       end=float(segment.end))
            for segment in segments_iter
        ]
        text = " ".join(segment.text for segment in segments).strip()
        return STTResult(
            text=text,
            language=getattr(info, "language", language),
            segments=segments,
            # The provider does not expose a calibrated utterance confidence.
            confidence_score=None,
            silence_detected=not bool(text),
        )
