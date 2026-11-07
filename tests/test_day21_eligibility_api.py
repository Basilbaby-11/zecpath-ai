from fastapi.testclient import TestClient

from api.main import app, CANDIDATE_SCORES, JOBS, RESUMES


def test_eligibility_endpoint_uses_saved_ats_result_and_profile(monkeypatch):
    job_id = "JOB-DAY21-API"
    candidate_id = "CAND-DAY21-API"
    monkeypatch.setitem(JOBS, job_id, {
        "title": "Python Developer", "description": "Test job",
        "parsed": {
            "job_id": job_id, "title": "Python Developer",
            "skills": [{"name": "Python", "requirement_type": "required"}],
        },
    })
    monkeypatch.setitem(RESUMES, "RES-DAY21-API", {
        "candidate_id": candidate_id, "job_id": job_id,
        "parsed_profile": {
            "candidate_id": candidate_id, "skills": ["Python"],
            "total_experience_months": 18,
        },
    })
    monkeypatch.setitem(CANDIDATE_SCORES, (candidate_id, job_id), {
        "candidate_id": candidate_id, "job_id": job_id, "overall_score": 80,
        "data_quality": "complete", "missing_components": [],
    })

    response = TestClient(app).get(
        f"/api/v1/jobs/{job_id}/candidates/{candidate_id}/eligibility"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "eligible"
    assert result["eligible_for_ai_screening"] is True
    assert result["checks"]


def test_eligibility_endpoint_returns_404_without_saved_ats_score(monkeypatch):
    job_id = "JOB-DAY21-NO-SCORE"
    monkeypatch.setitem(JOBS, job_id, {
        "title": "Backend Engineer", "description": "Test job",
        "parsed": {"job_id": job_id, "title": "Backend Engineer", "skills": []},
    })
    response = TestClient(app).get(
        f"/api/v1/jobs/{job_id}/candidates/UNKNOWN-CAND/eligibility"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ATS_SCORE_NOT_FOUND"
