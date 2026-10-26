import pytest
from fairness.resume_normalizer import normalize_resume, normalize_resume_batch

def test_normalizes_skills_and_deduplicates_case_insensitively():
    out = normalize_resume({"candidate_id":"C1", "skills":[" Python ", "python", {"name":"SQL"}]})
    assert out["skills"] == ["Python", "SQL"]
    assert out["experience"] == [] and out["education"] == []

def test_preserves_identity_only_in_personal_info():
    out = normalize_resume({"name":"Example", "email":"x@example.com"})
    assert out["personal_info"]["name"] == "Example"
    assert out["personal_info"]["email"] == "x@example.com"
    assert "name" not in out and "email" not in out

def test_rejects_non_object_resume():
    with pytest.raises(TypeError):
        normalize_resume("not a resume")

def test_batch_accepts_list_or_resumes_object():
    assert normalize_resume_batch({"resumes":[{}]})["total"] == 1
    assert normalize_resume_batch([{}, {}])["total"] == 2
