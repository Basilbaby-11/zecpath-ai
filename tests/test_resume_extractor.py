
import pytest
from pathlib import Path


from parsers.resume_extractor import clean_text, normalize_heading, extract_resume

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT_DIR / "data" / "sample_resumes"

def test_bullet_normalization():
    text = "Skills\n\u2022 Python\n\u2022 SQL"
    result = clean_text(text)

    assert "- Python" in result
    assert "- SQL" in result


def test_heading_normalization():
    assert normalize_heading("Technical Skills") == "SKILLS"
    assert normalize_heading("Work Experience") == "EXPERIENCE"


def test_extra_spaces():
    result = clean_text("Python    Developer")

    assert result == "Python Developer"


def test_unsupported_file(tmp_path):
    file_path = tmp_path / "resume.txt"
    file_path.write_text("Python developer", encoding="utf-8")

    with pytest.raises(ValueError):
        extract_resume(file_path)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_resume(tmp_path / "missing.pdf")
def test_extract_sample_pdf():
    pdf_file = SAMPLE_DIR / "sample_resume.pdf"

    result = extract_resume(pdf_file)

    assert result["extraction_status"] == "success"
    assert result["file_type"] == "pdf"
    assert result["word_count"] > 0
    assert result["extracted_text"].strip()


def test_extract_sample_docx():
    docx_file = SAMPLE_DIR / "sample_resume.docx"

    result = extract_resume(docx_file)

    assert result["extraction_status"] == "success"
    assert result["file_type"] == "docx"
    assert result["word_count"] > 0
    assert result["extracted_text"].strip()


def test_two_column_pdf_reading_order():
    from pathlib import Path
    from parsers.resume_extractor import read_pdf

    pdf_path = Path("data/sample_resumes/two_column_resume.pdf")
    text = read_pdf(pdf_path)

    assert "ALEX MORGAN" in text
    assert "Data Analyst Intern | Example Analytics" in text
    assert "Cleaned and validated datasets for weekly reporting." in text
    assert "Sales Insights Dashboard" in text

    assert text.index("PROFILE") < text.index("TECHNICAL SKILLS")
    assert text.index("TECHNICAL SKILLS") < text.index(
        "PROFESSIONAL EXPERIENCE"
    )
    assert text.index("PROFESSIONAL EXPERIENCE") < text.index("PROJECTS")


from pathlib import Path

import pytest
from parsers import resume_extractor as extractor

SAMPLES = Path(__file__).resolve().parents[1] / 'data' / 'sample_resumes'


@pytest.mark.parametrize('filename', ['image_only_resume.pdf', 'image_based_resume.docx'])
def test_image_resume_ocr(filename, tmp_path, monkeypatch):
    sample = SAMPLES / filename
    assert sample.exists(), f'Missing test input: {sample}'
    monkeypatch.setattr(extractor, 'TEXT_DIR', tmp_path)
    monkeypatch.setattr(extractor, 'OUTPUT_DIR', tmp_path)

    result = extractor.extract_resume(sample)
    text = result['extracted_text']
    assert result['extraction_status'] == 'success'
    assert 'JORDAN TAYLOR' in text
    assert 'JUNIOR DATA ANALYST' in text
    assert 'jordan.taylor@example.com' in text
    assert result['word_count'] >= 40
    assert (tmp_path / f'{sample.stem}_{sample.suffix[1:]}.txt').exists()
    assert (tmp_path / f'{sample.stem}_{sample.suffix[1:]}.json').exists()
