"""Day 17 regression and scenario tests for ATS scoring/ranking/shortlisting."""
import pytest

from scoring.ats_scoring_engine import load_weight_config, score_candidate
from ranking.candidate_ranking_engine import rank_candidates
from shortlisting.shortlisting_engine import classify_candidate


SCENARIOS = [
    # Category, role, component scores, expected decision from the reviewed test fixture.
    ("tech_fresher", "AI Engineer", {"skill_match": 90, "experience_relevance": 45, "education_alignment": 90, "semantic_similarity": 88}, "shortlisted"),
    ("tech_senior", "Python Developer", {"skill_match": 88, "experience_relevance": 92, "education_alignment": 75, "semantic_similarity": 90}, "shortlisted"),
    ("tech_mismatch", "AI Engineer", {"skill_match": 25, "experience_relevance": 30, "education_alignment": 65, "semantic_similarity": 28}, "rejected"),
    ("nontech_fresher", "HR Executive", {"skill_match": 82, "experience_relevance": 40, "education_alignment": 80, "semantic_similarity": 78}, "shortlisted"),
    ("nontech_senior", "Operations Manager", {"skill_match": 75, "experience_relevance": 88, "education_alignment": 80, "semantic_similarity": 82}, "shortlisted"),
    ("role_mismatch", "Python Developer", {"skill_match": 42, "experience_relevance": 35, "education_alignment": 70, "semantic_similarity": 38}, "rejected"),
    ("borderline", "AI Engineer", {"skill_match": 62, "experience_relevance": 58, "education_alignment": 70, "semantic_similarity": 60}, "review"),
    ("missing_data", "Python Developer", {"skill_match": 80}, "review"),
]


@pytest.mark.parametrize("case_id,role,components,expected", SCENARIOS)
def test_day17_role_and_experience_scenarios(case_id, role, components, expected):
    config = load_weight_config("config/ats_scoring_weights.json")
    scored = score_candidate(components, candidate_id=case_id, job_id="DAY17", role=role, weight_config=config)
    actual = classify_candidate(scored, {"shortlist_min": 70, "review_min": 50})
    assert actual["shortlisting_status"] == expected
    if case_id == "missing_data":
        assert actual["data_quality"] == "partial"
        assert actual["overall_score"] is not None


def test_day17_ranking_descending_and_missing_scores_last():
    rows = rank_candidates([
        {"candidate_id": "C3", "job_id": "J1", "overall_score": 60},
        {"candidate_id": "C1", "job_id": "J1", "overall_score": 90},
        {"candidate_id": "C2", "job_id": "J1", "overall_score": None},
    ])
    assert [row["candidate_id"] for row in rows] == ["C1", "C3", "C2"]
    assert [row["rank"] for row in rows] == [1, 2, None]


@pytest.mark.parametrize("scores", [
    {"skill_match": -1},
    {"skill_match": 101},
    {"skill_match": True},
])
def test_day17_invalid_component_scores_are_rejected(scores):
    with pytest.raises(ValueError):
        score_candidate(scores)


def test_day17_invalid_shortlisting_thresholds_are_rejected():
    with pytest.raises(ValueError):
        classify_candidate({"overall_score": 70}, {"shortlist_min": 60, "review_min": 80})
