from fairness.bias_evaluator import evaluate_bias_indicators

def test_score_validation_and_group_statistics():
    rows = ([{"overall_score":80,"audit_group":"A"} for _ in range(5)] +
            [{"overall_score":60,"audit_group":"B"} for _ in range(5)] +
            [{"overall_score":None,"audit_group":"A"},
             {"overall_score":101,"audit_group":"B"}])
    report = evaluate_bias_indicators(rows, group_field="audit_group", minimum_group_size=5)
    assert report["valid_score_count"] == 10
    assert report["missing_score_count"] == 1
    assert report["invalid_score_count"] == 1
    assert report["max_minus_min_group_mean_gap"] == 20

def test_small_groups_are_suppressed():
    rows = [{"overall_score":80,"audit_group":"small"} for _ in range(2)]
    report = evaluate_bias_indicators(rows, group_field="audit_group", minimum_group_size=5)
    assert report["group_statistics"] == {}
    assert report["max_minus_min_group_mean_gap"] is None
