import pytest

from eligibility.eligibility_engine import evaluate_eligibility, load_eligibility_rules, validate_rules


BASE_RULES = {
    "default": {
        "minimum_ats_score": 70,
        "review_ats_score": 50,
        "mandatory_skills": ["Python", "SQL"],
        "use_job_required_skills": False,
        "minimum_experience_months": 12,
        "maximum_experience_months": 60,
        "allowed_locations": ["Kochi"],
        "require_location_match": True,
        "required_availability": "immediate",
    },
    "roles": {},
    "job_overrides": {},
}


def evaluate(candidate=None, score=85, rules=None):
    return evaluate_eligibility(
        candidate=candidate or {
            "candidate_id": "C-1", "skills": ["Python", "SQL"],
            "total_experience_months": 24, "location": "Kochi, Kerala",
            "availability": "immediate",
        },
        ats_result={"candidate_id": "C-1", "job_id": "J-1", "overall_score": score,
                    "data_quality": "complete", "missing_components": []},
        job={"job_id": "J-1", "title": "Backend Engineer", "skills": []},
        rules_config=rules or BASE_RULES,
    )


def test_candidate_meeting_all_rules_is_eligible():
    result = evaluate()
    assert result["status"] == "eligible"
    assert result["eligible_for_ai_screening"] is True
    assert result["failed_rules"] == []
    assert result["review_rules"] == []


def test_low_ats_score_is_rejected():
    result = evaluate(score=40)
    assert result["status"] == "rejected"
    assert "ats_score" in result["failed_rules"]


def test_missing_mandatory_skill_is_rejected():
    result = evaluate(candidate={
        "candidate_id": "C-1", "skills": ["Python", "Java"],
        "total_experience_months": 24, "location": "Kochi", "availability": "immediate",
    })
    assert result["status"] == "rejected"
    assert "mandatory_skills" in result["failed_rules"]


def test_experience_below_range_is_rejected():
    result = evaluate(candidate={
        "candidate_id": "C-1", "skills": ["Python", "SQL"],
        "total_experience_months": 6, "location": "Kochi", "availability": "immediate",
    })
    assert result["status"] == "rejected"
    assert "experience_range" in result["failed_rules"]


def test_missing_experience_data_goes_to_review():
    result = evaluate(candidate={"candidate_id": "C-1", "skills": ["Python", "SQL"],
                                "location": "Kochi", "availability": "immediate"})
    assert result["status"] == "review"
    assert "experience_range" in result["review_rules"]


def test_missing_location_or_availability_goes_to_review():
    result = evaluate(candidate={"candidate_id": "C-1", "skills": ["Python", "SQL"],
                                "total_experience_months": 24})
    assert result["status"] == "review"
    assert "location" in result["review_rules"]
    assert "availability" in result["review_rules"]


def test_partial_ats_data_goes_to_review_not_auto_reject():
    result = evaluate_eligibility(
        candidate={"candidate_id": "C-1", "skills": ["Python", "SQL"],
                   "total_experience_months": 24, "location": "Kochi", "availability": "immediate"},
        ats_result={"overall_score": 90, "data_quality": "partial", "missing_components": ["education_alignment"]},
        job={"job_id": "J-1", "title": "Backend Engineer", "skills": []},
        rules_config=BASE_RULES,
    )
    assert result["status"] == "review"
    assert "ats_score" in result["review_rules"]


def test_role_and_job_specific_rules_override_defaults():
    cfg = {
        "default": {"minimum_ats_score": 70, "review_ats_score": 50, "mandatory_skills": [],
                    "use_job_required_skills": False, "minimum_experience_months": None,
                    "maximum_experience_months": None, "allowed_locations": [],
                    "require_location_match": False, "required_availability": None},
        "roles": {"Python Developer": {"minimum_ats_score": 65}},
        "job_overrides": {"J-1": {"minimum_ats_score": 80}},
    }
    result = evaluate_eligibility(
        candidate={"candidate_id": "C-1", "skills": ["Python"]},
        ats_result={"overall_score": 75, "data_quality": "complete", "missing_components": []},
        job={"job_id": "J-1", "title": "Python Developer", "skills": []}, rules_config=cfg,
    )
    assert result["status"] == "review"
    assert result["rules_source"] == "job:J-1"
    assert result["rules_applied"]["minimum_ats_score"] == 80


def test_invalid_threshold_configuration_is_rejected():
    with pytest.raises(ValueError):
        validate_rules({"minimum_ats_score": 40, "review_ats_score": 60})


def test_config_file_is_loadable():
    config = load_eligibility_rules("config/eligibility_rules.json")
    assert config["roles"]["AI Engineer"]["minimum_ats_score"] == 72
