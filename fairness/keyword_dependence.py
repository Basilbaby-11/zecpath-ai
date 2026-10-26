"""Diagnostics for keyword dependence and semantic-aware score comparisons."""
from __future__ import annotations
from statistics import mean
from typing import Any, Mapping, Sequence


def evaluate_keyword_dependence(records: Sequence[Mapping[str, Any]], *, keyword_field: str = "skill_match", semantic_field: str = "semantic_similarity", threshold: float = 10.0) -> dict[str, Any]:
    """Report how often keyword and semantic scores diverge by at least threshold points."""
    paired = []
    missing = 0
    for row in records:
        try:
            keyword, semantic = row.get(keyword_field), row.get(semantic_field)
            if keyword is None or semantic is None or isinstance(keyword, bool) or isinstance(semantic, bool):
                missing += 1
                continue
            keyword, semantic = float(keyword), float(semantic)
            if not (0 <= keyword <= 100 and 0 <= semantic <= 100):
                missing += 1
                continue
            paired.append((keyword, semantic, abs(keyword - semantic)))
        except (TypeError, ValueError):
            missing += 1
    return {
        "records_checked": len(records), "paired_valid_records": len(paired),
        "records_missing_or_invalid_components": missing,
        "mean_absolute_keyword_semantic_gap": round(mean([x[2] for x in paired]), 2) if paired else None,
        "gap_threshold_points": threshold,
        "records_with_large_gap": sum(x[2] >= threshold for x in paired),
        "interpretation": "Diagnostic only: a large gap flags cases for review; it does not prove keyword bias or fairness.",
    }


def compare_keyword_and_semantic_aware_rankings(
    records: Sequence[Mapping[str, Any]],
    *,
    baseline_field: str = "overall_score",
    semantic_field: str = "semantic_similarity",
    semantic_weight: float = 0.20,
    top_n: int = 10,
    id_fields: tuple[str, ...] = ("candidate_id", "resume_id", "candidate_job_id", "job_id"),
) -> dict[str, Any]:
    """Compare baseline and experimental review rankings for the same score records.

    This reports ranking movement; it does not establish improved fairness or hiring
    validity. The baseline score is never overwritten.
    """
    if not 0 <= semantic_weight <= 1:
        raise ValueError("semantic_weight must be between 0 and 1.")
    if top_n < 1:
        raise ValueError("top_n must be at least 1.")

    valid = []
    skipped = 0
    seen_ids: set[str] = set()
    for index, row in enumerate(records):
        try:
            baseline_raw = row.get(baseline_field)
            semantic_raw = row.get(semantic_field)
            if (baseline_raw is None or semantic_raw is None
                or isinstance(baseline_raw, bool) or isinstance(semantic_raw, bool)):
                skipped += 1
                continue
            baseline, semantic = float(baseline_raw), float(semantic_raw)
            if not (0 <= baseline <= 100 and 0 <= semantic <= 100):
                skipped += 1
                continue
            identifier = next((str(row[field]) for field in id_fields
                               if row.get(field) is not None and str(row[field]).strip()), f"record_{index}")
            if identifier in seen_ids:
                identifier = f"{identifier}#{index}"
            seen_ids.add(identifier)
            review = round((1 - semantic_weight) * baseline + semantic_weight * semantic, 2)
            valid.append({"id": identifier, "baseline": baseline, "review": review,
                          "semantic_similarity": semantic})
        except (TypeError, ValueError):
            skipped += 1

    baseline_order = sorted(valid, key=lambda r: (-r["baseline"], r["id"]))
    review_order = sorted(valid, key=lambda r: (-r["review"], r["id"]))
    baseline_rank = {r["id"]: i + 1 for i, r in enumerate(baseline_order)}
    review_rank = {r["id"]: i + 1 for i, r in enumerate(review_order)}
    movements = [
        {"id": identifier, "baseline_score": next(r["baseline"] for r in valid if r["id"] == identifier),
         "semantic_aware_review_score": next(r["review"] for r in valid if r["id"] == identifier),
         "baseline_rank": baseline_rank[identifier], "review_rank": review_rank[identifier],
         "rank_change": baseline_rank[identifier] - review_rank[identifier]}
        for identifier in baseline_rank
    ]
    movements.sort(key=lambda r: (-abs(r["rank_change"]), r["id"]))
    n = min(top_n, len(valid))
    baseline_top = {r["id"] for r in baseline_order[:n]}
    review_top = {r["id"] for r in review_order[:n]}
    return {
        "records_checked": len(records),
        "valid_records_compared": len(valid),
        "records_skipped_missing_or_invalid": skipped,
        "semantic_weight": semantic_weight,
        "top_n": n,
        "baseline_score_field": baseline_field,
        "experimental_score_formula": "(1 - semantic_weight) * baseline_score + semantic_weight * semantic_similarity",
        "top_n_overlap_count": len(baseline_top & review_top),
        "top_n_overlap_rate": round(len(baseline_top & review_top) / n, 4) if n else None,
        "mean_absolute_rank_change": round(mean([abs(r["rank_change"]) for r in movements]), 2) if movements else None,
        "largest_rank_changes": movements[:min(10, len(movements))],
        "interpretation": "Ranking comparison only. Rank movement is not proof of reduced bias or improved validity; review examples against job-related criteria.",
    }
