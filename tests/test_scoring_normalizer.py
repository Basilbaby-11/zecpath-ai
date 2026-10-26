import pytest
from fairness.scoring_normalizer import normalize_component_score, calculate_semantic_aware_review_score

@pytest.mark.parametrize("value,expected", [(0,0), (50,50), (100,100)])
def test_100_point_scale(value, expected):
    assert normalize_component_score(value) == expected

def test_converts_declared_0_to_10_scale():
    assert normalize_component_score(5, source_min=0, source_max=10) == 50

def test_rejects_invalid_range_and_boolean():
    with pytest.raises(ValueError):
        normalize_component_score(101)
    with pytest.raises(ValueError):
        normalize_component_score(True)
    with pytest.raises(ValueError):
        normalize_component_score(3, source_min=5, source_max=5)

def test_review_score_blends_and_preserves_missing():
    assert calculate_semantic_aware_review_score(80, 100, semantic_weight=.2) == 84
    assert calculate_semantic_aware_review_score(None, 100) is None
