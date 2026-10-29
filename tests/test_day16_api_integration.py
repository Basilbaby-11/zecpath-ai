from pathlib import Path

from api.main import ScoreRequest, ShortlistRequest, ShortlistCandidate, score_adapter, build_shortlist


def test_score_adapter_uses_repository_scoring_engine():
    result = score_adapter(
        "CAND-TEST",
        ScoreRequest(
            job_id="JOB-TEST",
            role="Python Developer",
            component_scores={
                "skill_match": 80,
                "experience_relevance": 70,
                "education_alignment": 60,
                "semantic_similarity": 90,
            },
        ),
    )
    assert result["candidate_id"] == "CAND-TEST"
    assert result["job_id"] == "JOB-TEST"
    assert isinstance(result["overall_score"], float)
    assert result["overall_score"] > 0


def test_shortlist_uses_repository_ranking_and_classification():
    payload = ShortlistRequest(
        candidates=[
            ShortlistCandidate(candidate_id="CAND-2", overall_score=60),
            ShortlistCandidate(candidate_id="CAND-1", overall_score=85),
            ShortlistCandidate(candidate_id="CAND-3", overall_score=None),
        ],
        top_n=3,
        shortlist_threshold=75,
        review_threshold=50,
    )
    result = build_shortlist("JOB-TEST", payload)
    rows = result["ranked_candidates"]
    assert rows[0]["candidate_id"] == "CAND-1"
    assert rows[0]["shortlisting_status"] == "shortlisted"
    assert rows[1]["shortlisting_status"] == "review"
    assert rows[2]["shortlisting_status"] == "review"
    assert result["decision_policy"]["human_review_required"] is True


def test_upload_rejects_unsupported_file_type():
    from fastapi.testclient import TestClient
    from api.main import app
    response = TestClient(app).post(
        "/api/v1/resumes",
        data={"candidate_id": "CAND-TEST"},
        files={"file": ("resume.txt", b"not a resume", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RESUME_FORMAT"
