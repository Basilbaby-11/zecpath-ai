
from ats_engine.matcher import calculate_match_score


def test_exact_skill_match():
    score = calculate_match_score(
        ["Python", "SQL"],
        ["Python", "SQL"],
    )
    assert score == 100.0


def test_partial_skill_match():
    score = calculate_match_score(
        ["Python", "SQL"],
        ["Python"],
    )
    assert score == 50.0


def test_no_required_skills():
    assert calculate_match_score([], ["Python"]) == 0.0


def test_skill_matching_ignores_case():
    assert calculate_match_score(
        ["PYTHON"],
        ["python"],
    ) == 100.0
