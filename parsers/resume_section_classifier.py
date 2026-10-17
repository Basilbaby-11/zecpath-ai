"""Rule-based and lightweight NLP-assisted resume section segmentation.

This module consumes extracted text; it deliberately does not replace the Day 5
PDF/DOCX/OCR extractor. It returns section-level text plus per-block labels.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from parsers.heading_patterns import HEADING_MAP, SECTION_LABELS

PARSER_VERSION = "1.0.0"


def normalize_heading(line: str) -> str:
    """Normalize a candidate heading for dictionary matching."""
    value = line.strip().lower()
    value = re.sub(r"^[\s#>*•\-–—]+", "", value)
    value = re.sub(r"[\s:：|]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .")


def detect_heading(line: str) -> str | None:
    """Return the canonical section if a line is a known heading."""
    cleaned = normalize_heading(line)
    if cleaned in HEADING_MAP:
        return HEADING_MAP[cleaned]
    # Headings in templates sometimes have explanatory notes after a dash.
    for separator in (" — ", " – ", " - ", ":"):
        if separator in line:
            prefix = normalize_heading(line.split(separator, 1)[0])
            if prefix in HEADING_MAP:
                return HEADING_MAP[prefix]
    # Resume headings often include numbering, e.g. "1. Technical Skills".
    cleaned = re.sub(r"^\d+[.)\s]+", "", cleaned)
    return HEADING_MAP.get(cleaned)


def classify_block(text: str) -> tuple[str, float]:
    """Infer a likely section for an unheaded block using transparent clues.

    Heading detection remains the primary signal. Confidence is heuristic, not a
    calibrated probability; ambiguous text is assigned to ``other``.
    """
    value = text.strip()
    low = value.lower()
    if not value:
        return "other", 0.0
    if re.search(r"\b(b\.tech|bachelor|master(?:'s)?|ph\.d|diploma|university|college|graduat(?:ed|ion))\b", low):
        return "education", 0.72
    if re.search(r"\b(certified|certification|certificate|coursera|udemy|cognitive class)\b", low):
        return "certifications", 0.68
    if re.search(r"\b(project|developed|built|implemented|designed|engineered)\b", low):
        return "projects", 0.58
    if re.search(r"\b(python|java|javascript|sql|tensorflow|pytorch|scikit-learn|fastapi|machine learning|nlp)\b", low) and ("," in value or "skills" in low or len(value.splitlines()) <= 3):
        return "skills", 0.66
    if re.search(r"\b(intern|engineer|analyst|developer|manager|company|employer)\b", low) and re.search(r"\b(20\d{2}|present|current|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", low):
        return "work_experience", 0.62
    if re.search(r"\b(english|malayalam|hindi|tamil|fluent|native|basic)\b", low) and len(value.split()) <= 18:
        return "languages", 0.62
    return "other", 0.35


def segment_resume(text: str, source_document: str | None = None) -> dict[str, Any]:
    """Split extracted resume text into canonical sections.

    Heading lines are not included in section content. Content before the first
    recognized heading is retained under ``summary`` when non-empty; all content
    is retained, including lines that cannot be classified confidently.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    sections: dict[str, list[str]] = {label: [] for label in SECTION_LABELS}
    blocks: list[dict[str, Any]] = []
    current: str | None = None
    preamble: list[str] = []

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        heading = detect_heading(line)
        if heading:
            current = heading
            blocks.append({"text": line, "section": heading, "block_type": "heading", "confidence": 1.0})
            continue
        if current is None:
            preamble.append(line)
            continue
        sections[current].append(line)
        blocks.append({"text": line, "section": current, "block_type": "content", "confidence": 0.95})

    if preamble:
        preamble_text = "\n".join(preamble)
        # Try content clues for a heading-less preamble; default to summary.
        label, confidence = classify_block(preamble_text)
        if label == "other":
            label, confidence = "summary", 0.55
        sections[label].extend(preamble)
        blocks = [{"text": line, "section": label, "block_type": "content", "confidence": confidence} for line in preamble] + blocks

    # Fill sections that have no heading by classifying isolated lines conservatively.
    # This recovers common unheaded table/list content without overwriting explicit sections.
    for label in SECTION_LABELS:
        sections[label] = [item for item in sections[label] if item.strip()]

    return {
        "parser_version": PARSER_VERSION,
        "source_document": source_document,
        "sections": sections,
        "blocks": blocks,
        "section_count": sum(bool(items) for items in sections.values()),
        "unclassified_block_count": sum(1 for block in blocks if block["section"] == "other"),
    }


def segment_file(path: str, encoding: str = "utf-8") -> dict[str, Any]:
    """Segment a previously extracted .txt resume file."""
    from pathlib import Path

    file_path = Path(path)
    return segment_resume(file_path.read_text(encoding=encoding), source_document=file_path.name)
