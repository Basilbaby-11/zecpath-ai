import pytest
from fairness.resume_normalizer import normalize_resume, normalize_resume_batch
from fairness.scoring_normalizer import normalize_component_score, normalize_score_record
from fairness.personal_attribute_masker import mask_personal_attributes
from fairness.bias_evaluator import evaluate_bias_indicators


def test_normalize_combined_resume_shape_and_deduplicate_skills():
    row = normalize_resume({"candidate_id": "C1", "source_document": "resume.pdf", "skills": ["Python", "python", {"name": "SQL"}], "experience": [], "personal_info": {"name": "Alex"}})
    assert row["skills"] == ["Python", "SQL"]
    assert row["candidate_id"] == "C1"
    assert row["personal_info"]["name"] == "Alex"


def test_normalize_batch_accepts_pipeline_payload():
    result = normalize_resume_batch({"resumes": [{"candidate_id": "C1"}, {"candidate_id": "C2"}]})
    assert result["total"] == 2


def test_score_normalization_and_missing_values():
    assert normalize_component_score(0.5, source_min=0, source_max=1) == 50.0
    assert normalize_component_score(None) is None
    assert normalize_score_record({"skill": 80}) == {"skill": 80.0}


def test_score_normalization_rejects_ambiguous_out_of_range_input():
    with pytest.raises(ValueError):
        normalize_component_score(101)


def test_masker_does_not_mutate_original_and_removes_identifiers():
    original = {"candidate_id": "C1", "personal_info": {"name": "Alex", "email": "alex@example.com"}, "summary": "Contact alex@example.com"}
    masked = mask_personal_attributes(original)
    assert "personal_info" in original
    assert "personal_info" not in masked
    assert "alex@example.com" not in masked["summary"]
    assert masked["candidate_id"] == "C1"


def test_bias_report_quality_and_group_gap():
    rows = ([{"overall_score": 80, "audit_group": "A"}] * 5) + ([{"overall_score": 60, "audit_group": "B"}] * 5) + [{"overall_score": None}]
    report = evaluate_bias_indicators(rows, group_field="audit_group")
    assert report["missing_score_count"] == 1
    assert report["max_minus_min_group_mean_gap"] == 20.0
    assert report["group_statistics"]["A"]["n"] == 5


def test_masker_preserves_employment_date_ranges_and_redacts_phone():
    row = {"source_text": "Backend Developer | Example Co | 2021-01 - 2024-01", "contact_text": "Call +1 (415) 555-0123"}
    masked = mask_personal_attributes(row)
    assert "2021-01 - 2024-01" in masked["source_text"]
    assert "[PHONE_REDACTED]" in masked["contact_text"]
    assert "555-0123" not in masked["contact_text"]


def test_masker_preserves_standalone_year_month_dates():
    masked = mask_personal_attributes({"text": "Experience: 2024-02 - Present"})
    assert "2024-02 - Present" in masked["text"]
