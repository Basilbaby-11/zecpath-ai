"""Clean raw ASR text while preserving the original transcript separately."""
from __future__ import annotations

import re
import unicodedata

_FILLERS = ("you know", "i mean", "kind of", "sort of", "uh", "um", "erm", "hmm", "ah")


def clean_transcript(
    text: str, *, remove_fillers: bool = True, lowercase: bool = False
) -> str:
    """Return readable transcript text; never mutate or overwrite raw input."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    if remove_fillers:
        for filler in sorted(_FILLERS, key=len, reverse=True):
            cleaned = re.sub(
                rf"(?i)(?<!\w){re.escape(filler)}(?!\w)", " ", cleaned
            )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^[,;:]+\s*", "", cleaned)
    cleaned = re.sub(r"\s*[,;:]+\s*([.!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([,;:])(?=\S)", r"\1 ", cleaned)
    cleaned = re.sub(r"([.!?]){2,}", r"\1", cleaned)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned[-1] not in ".!?":
            cleaned += "."
    return cleaned.lower() if lowercase else cleaned
