import pytest
from fairness.keyword_dependence import evaluate_keyword_dependence, compare_keyword_and_semantic_aware_rankings

def test_gap_diagnostic_flags_large_gap():
    report = evaluate_keyword_dependence([{"skill_match":90,"semantic_similarity":60}])
    assert report["records_with_large_gap"] == 1
    assert report["mean_absolute_keyword_semantic_gap"] == 30

def test_ranking_comparison_reports_movement_without_claiming_fairness():
    rows = [
        {"candidate_id":"A","overall_score":90,"semantic_similarity":40},
        {"candidate_id":"B","overall_score":80,"semantic_similarity":100},
        {"candidate_id":"C","overall_score":70,"semantic_similarity":70},
    ]
    report = compare_keyword_and_semantic_aware_rankings(rows, semantic_weight=.5, top_n=2)
    assert report["valid_records_compared"] == 3
    assert report["top_n_overlap_count"] == 1
    assert "not proof" in report["interpretation"]

def test_invalid_weight_rejected():
    with pytest.raises(ValueError):
        compare_keyword_and_semantic_aware_rankings([], semantic_weight=1.5)
