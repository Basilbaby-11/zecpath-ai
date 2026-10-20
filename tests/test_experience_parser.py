from datetime import date

from parsers.experience_parser import analyze_timeline, duration_months, parse_experience


def test_extracts_common_experience_format():
    result = parse_experience("Data Analyst | Acme Analytics | Jan 2022 - Mar 2024", candidate_id="CAND_1", as_of=date(2024, 4, 1))
    assert len(result["experiences"]) == 1
    item = result["experiences"][0]
    assert item["designation"] == "Data Analyst"
    assert item["employer"] == "Acme Analytics"
    assert item["start_date"] == "2022-01"
    assert item["end_date"] == "2024-03"
    assert item["duration_months"] == 27


def test_current_role_duration():
    assert duration_months("2024-01", None, True, date(2024, 3, 1)) == 3


def test_timeline_does_not_double_count_overlap_and_detects_gap():
    items = [
        {"experience_id": "E1", "start_date": "2020-01", "end_date": "2020-12", "is_current": False},
        {"experience_id": "E2", "start_date": "2020-10", "end_date": "2021-03", "is_current": False},
        {"experience_id": "E3", "start_date": "2021-07", "end_date": "2021-12", "is_current": False},
    ]
    result = analyze_timeline(items)
    assert result["total_experience_months"] == 21
    assert result["overlapping_periods"]
    assert result["employment_gaps"] == [{"start_date": "2021-04", "end_date": "2021-06", "duration_months": 3}]


def test_invalid_input_raises_type_error():
    import pytest
    with pytest.raises(TypeError):
        parse_experience(None)
