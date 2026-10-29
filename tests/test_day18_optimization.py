from pathlib import Path

import pytest

from parsers.resume_extractor import clean_text, normalize_heading, extract_resume
from ats_engine.semantic_matching_engine import SemanticMatchingEngine


class CountingEncoder:
    def __init__(self):
        self.calls = 0
        self.last_batch_size = 0

    def encode(self, sentences, **kwargs):
        import numpy as np
        self.calls += 1
        self.last_batch_size = len(sentences)
        # Stable toy vectors for functional tests only.
        return np.array([[float(len(s) + 1), float(sum(map(ord, s)) % 97 + 1)] for s in sentences])


def test_semantic_matching_batches_nonempty_sections_into_one_encoder_call():
    encoder = CountingEncoder()
    engine = SemanticMatchingEngine(encoder=encoder)
    result = engine.compare(
        {"skills": ["Python", "SQL"], "experience": "Built APIs", "projects": ["ATS"], "professional_summary": "Developer"},
        {"required_skills": ["Python"], "responsibilities": "Build APIs", "relevant_projects": ["Hiring system"], "title": "Developer", "description": "Software role"},
    )
    assert result["overall_category"] in {"strong", "moderate", "weak"}
    assert encoder.calls == 1
    assert encoder.last_batch_size == 8


def test_semantic_matching_handles_empty_sections_without_embedding_them():
    encoder = CountingEncoder()
    result = SemanticMatchingEngine(encoder=encoder).compare(
        {"skills": [], "experience": "", "projects": [], "professional_summary": ""},
        {"required_skills": ["Python"], "responsibilities": "", "relevant_projects": [], "title": "Developer", "description": ""},
    )
    assert result["similarity_scores"]["skills"]["status"] == "insufficient_data"
    assert encoder.calls == 0
    assert result["overall_category"] == "insufficient_data"


def test_noisy_resume_text_normalization():
    raw = "  SKILLS:  \r\nPython,SQL\u00a0\r\n---\r\n\r\nEXPERIENCE :\r\nBuilt  APIs  "
    cleaned = clean_text(raw)
    assert "SKILLS" in cleaned
    assert "Python, SQL" in cleaned
    assert "EXPERIENCE" in cleaned
    assert "Built APIs" in cleaned
    assert normalize_heading("  Work Experience: ") == "EXPERIENCE"


def test_extractor_rejects_unsupported_file_type(tmp_path: Path):
    path = tmp_path / "resume.txt"
    path.write_text("A plain text resume that is long enough.", encoding="utf-8")
    with pytest.raises(ValueError, match="Only PDF and DOCX"):
        extract_resume(path)
