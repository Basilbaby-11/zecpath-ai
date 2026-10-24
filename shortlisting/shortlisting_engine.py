"""Configurable shortlisting classification for recruiter decision support."""
from __future__ import annotations
from typing import Any, Mapping

DEFAULT_THRESHOLDS = {"shortlist_min": 75.0, "review_min": 50.0}

def validate_thresholds(config: Mapping[str, Any] | None = None) -> dict[str, float]:
    cfg = dict(config or DEFAULT_THRESHOLDS)
    try:
        shortlist_min = float(cfg["shortlist_min"])
        review_min = float(cfg["review_min"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Thresholds must define numeric shortlist_min and review_min.") from exc
    if not (0 <= review_min <= shortlist_min <= 100):
        raise ValueError("Thresholds must satisfy 0 <= review_min <= shortlist_min <= 100.")
    return {"shortlist_min": shortlist_min, "review_min": review_min}

def classify_candidate(candidate: Mapping[str, Any],
                       thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Add a status and reason; missing scores go to manual review."""
    cfg = validate_thresholds(thresholds)
    row = dict(candidate)
    score = row.get("overall_score")
    if score is None:
        status, reason = "review", "ATS score is unavailable; manual review is required."
    else:
        try:
            score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid overall_score: {score!r}") from exc
        if not 0 <= score <= 100:
            raise ValueError("overall_score must be between 0 and 100.")
        row["overall_score"] = round(score, 2)
        if score >= cfg["shortlist_min"]:
            status, reason = "shortlisted", f"Score meets the shortlist threshold ({cfg['shortlist_min']:.2f})."
        elif score >= cfg["review_min"]:
            status, reason = "review", f"Score is in the manual-review range ({cfg['review_min']:.2f} to below {cfg['shortlist_min']:.2f})."
        else:
            status, reason = "rejected", f"Score is below the review threshold ({cfg['review_min']:.2f})."
    row["shortlisting_status"] = status
    row["shortlisting_reason"] = reason
    return row
