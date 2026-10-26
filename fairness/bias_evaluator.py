"""Descriptive fairness checks for ATS score batches; not a legal compliance test."""
from __future__ import annotations
from collections import defaultdict
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence


def evaluate_bias_indicators(records: Sequence[Mapping[str, Any]], *, group_field: str | None = None, score_field: str = "overall_score", minimum_group_size: int = 5) -> dict[str, Any]:
    """Summarize score quality and, optionally, pre-approved audit-group gaps.

    Group attributes must be supplied from a lawful, separately governed audit
    dataset; this function never infers protected traits from names or resumes.
    Small groups are suppressed by default to reduce re-identification risk.
    """
    scores: list[float] = []
    missing = invalid = 0
    groups: dict[str, list[float]] = defaultdict(list)
    for row in records:
        raw = row.get(score_field)
        if raw is None:
            missing += 1
            continue
        if isinstance(raw, bool):
            invalid += 1
            continue
        try:
            score = float(raw)
        except (TypeError, ValueError):
            invalid += 1
            continue
        if not 0 <= score <= 100:
            invalid += 1
            continue
        scores.append(score)
        if group_field:
            group = row.get(group_field)
            if group is not None and str(group).strip():
                groups[str(group)].append(score)
    group_stats: dict[str, Any] = {}
    eligible = {name: vals for name, vals in groups.items() if len(vals) >= minimum_group_size}
    for name, vals in sorted(eligible.items()):
        group_stats[name] = {"n": len(vals), "mean_score": round(mean(vals), 2), "pass_rate_75": round(sum(s >= 75 for s in vals) / len(vals), 4)}
    mean_gap = None
    pass_rate_gap = None
    if len(group_stats) >= 2:
        means = [item["mean_score"] for item in group_stats.values()]
        rates = [item["pass_rate_75"] for item in group_stats.values()]
        mean_gap = round(max(means) - min(means), 2)
        pass_rate_gap = round(max(rates) - min(rates), 4)
    warnings = []
    if missing: warnings.append("Some candidates have missing scores; inspect upstream data quality.")
    if invalid: warnings.append("Some scores are invalid or outside 0-100 and were excluded.")
    if group_field and len(group_stats) < 2: warnings.append("Insufficient eligible audit groups for a group comparison; no conclusion about fairness can be drawn.")
    if mean_gap is not None and mean_gap >= 10: warnings.append("Observed group mean-score gap is at least 10 points; investigate job relevance, sample composition, and pipeline behavior.")
    return {"report_version": "1.0.0", "score_field": score_field, "total_records": len(records), "valid_score_count": len(scores), "missing_score_count": missing, "invalid_score_count": invalid, "overall": {"mean": round(mean(scores), 2) if scores else None, "population_std_dev": round(pstdev(scores), 2) if scores else None, "min": min(scores) if scores else None, "max": max(scores) if scores else None}, "group_field": group_field, "groups_suppressed_below_minimum": minimum_group_size, "group_statistics": group_stats, "max_minus_min_group_mean_gap": mean_gap, "max_minus_min_group_pass_rate_gap": pass_rate_gap, "warnings": warnings, "limitations": ["Descriptive indicators do not establish causation or legal compliance.", "Do not infer protected traits from names, photos, locations, or resume text.", "Review job-related validity, sample size, data quality, and human-review outcomes before acting on disparities."]}
