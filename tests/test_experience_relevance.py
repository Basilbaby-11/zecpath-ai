from ats_engine.experience_relevance_engine import role_similarity, score_experience_relevance


def test_related_roles_have_similarity():
    result = role_similarity("Python Developer", "AI Engineer", ["Python", "FastAPI"], ["Python", "Machine Learning"])
    assert result["score"] > 0
    assert result["relationship"] in {"high", "moderate", "low"}


def test_exact_role_is_full_title_similarity():
    result = role_similarity("Data Analyst", "Data Analyst")
    assert result["title_similarity"] == 100.0


def test_relevance_scores_rank_experiences():
    experiences = [
        {"experience_id": "E1", "designation": "Python Developer", "employer": "A", "skills_used": ["Python", "SQL"], "description": "Built APIs"},
        {"experience_id": "E2", "designation": "Sales Executive", "employer": "B", "skills_used": ["Sales"], "description": "Managed accounts"},
    ]
    result = score_experience_relevance(experiences, {"title": "AI Engineer", "required_skills": ["Python", "Machine Learning"], "responsibilities": ["Build Python models"]})
    assert result["experience_scores"][0]["relevance_score"] >= result["experience_scores"][1]["relevance_score"]
    assert result["decision_support_only"] is True
