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


def classify_candidate(candidate: Mapping[str, Any],thresholds: Mapping[str, Any] | None = None,) -> dict[str, Any]:
    """Classify candidates; incomplete data always requires manual review."""
    cfg = validate_thresholds(thresholds)
    row = dict(candidate)

    score = row.get("overall_score")
    data_quality = row.get("data_quality")
    missing_components = row.get("missing_components", [])

    # Incomplete scoring data must never automatically shortlist or reject.
    if (
        score is None
        or data_quality in {"partial", "insufficient"}
        or bool(missing_components)
    ):
        status = "review"
        reason = (
            "Scoring data is missing or incomplete; "
            "manual review is required."
        )

    else:
        try:
            score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid overall_score: {score!r}"
            ) from exc

        if not 0 <= score <= 100:
            raise ValueError("overall_score must be between 0 and 100.")

        row["overall_score"] = round(score, 2)

        if score >= cfg["shortlist_min"]:
            status = "shortlisted"
            reason = (
                f"Score meets the shortlist threshold "
                f"({cfg['shortlist_min']:.2f})."
            )
        elif score >= cfg["review_min"]:
            status = "review"
            reason = (
                f"Score is in the manual-review range "
                f"({cfg['review_min']:.2f} to below "
                f"{cfg['shortlist_min']:.2f})."
            )
        else:
            status = "rejected"
            reason = (
                f"Score is below the review threshold "
                f"({cfg['review_min']:.2f})."
            )

    row["shortlisting_status"] = status
    row["shortlisting_reason"] = reason
    return row
