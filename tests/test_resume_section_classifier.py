import pytest

from parsers.resume_section_classifier import classify_block, detect_heading, segment_resume


@pytest.mark.parametrize(("heading", "expected"), [
    ("Technical Skills", "skills"),
    ("PROFESSIONAL EXPERIENCE:", "work_experience"),
    ("Academic Background", "education"),
    ("Certificates & Certifications", "certifications"),
    ("Personal Projects", "projects"),
    ("1. Education", "education"),
    ("Soft Skills", "soft_skills"),
])
def test_heading_variations(heading, expected):
    assert detect_heading(heading) == expected


def test_segments_multiple_sections_and_preserves_content():
    text = """Candidate Name\nAI developer\nTECHNICAL SKILLS\nPython, SQL, TensorFlow\nWORK EXPERIENCE\nAI Intern | Example Co | 2025\nEDUCATION\nB.Tech in AI & Data Science\nPROJECTS\nBuilt a resume parser\nCERTIFICATIONS\nPython for Data Science"""
    result = segment_resume(text, "sample.txt")
    assert result["source_document"] == "sample.txt"
    assert "Python, SQL, TensorFlow" in result["sections"]["skills"]
    assert "AI Intern | Example Co | 2025" in result["sections"]["work_experience"]
    assert "B.Tech in AI & Data Science" in result["sections"]["education"]
    assert "Built a resume parser" in result["sections"]["projects"]
    assert "Python for Data Science" in result["sections"]["certifications"]
    assert all(block["section"] for block in result["blocks"])


def test_unknown_content_is_not_discarded():
    result = segment_resume("Mysterious headingless content with no known clues")
    assert result["sections"]["summary"] == ["Mysterious headingless content with no known clues"]


def test_empty_and_invalid_input():
    assert segment_resume("")["section_count"] == 0
    with pytest.raises(TypeError):
        segment_resume(None)


def test_content_clue_classification():
    assert classify_block("B.Tech in Computer Science") [0] == "education"
