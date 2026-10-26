"""Normalize ATS component scores and calculate a semantic-aware review score.

This is a transparent secondary review score, not a validated hiring decision.
It retains the original ATS score and does not silently replace it.
"""
from __future__ import annotations
from typing import Any, Mapping

SCORE_COMPONENTS = (
    "skill_match", "experience_relevance", "education_alignment",
    "semantic_similarity", "overall_score",
)


def normalize_component_score(value: Any, *, source_min: float = 0.0, source_max: float = 100.0) -> float | None:
    """Convert a score from a declared range to 0..100; preserve missing as None."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid scores.")
    try:
        score, low, high = float(value), float(source_min), float(source_max)
    except (TypeError, ValueError) as exc:
        raise ValueError("Score and source bounds must be numeric.") from exc
    if high <= low:
        raise ValueError("source_max must be greater than source_min.")
    if not low <= score <= high:
        raise ValueError(f"Score {score} is outside declared range [{low}, {high}].")
    return round((score - low) / (high - low) * 100.0, 2)


def normalize_score_record(scores: Mapping[str, Any], *, ranges: Mapping[str, tuple[float, float]] | None = None) -> dict[str, float | None]:
    if not isinstance(scores, Mapping):
        raise TypeError("Scores must be a mapping/object.")
    ranges = ranges or {}
    result = {}
    for name, value in scores.items():
        low, high = ranges.get(name, (0.0, 100.0))
        result[str(name)] = normalize_component_score(value, source_min=low, source_max=high)
    return result


def calculate_semantic_aware_review_score(
    overall_score: Any, semantic_similarity: Any, *, semantic_weight: float = 0.20
) -> float | None:
    """Blend existing overall score with semantic similarity for review comparison.

    Default: 80% existing ATS overall score + 20% semantic similarity. This adds
    weight to contextual similarity to reduce reliance on exact keyword overlap.
    Missing values are not invented; invalid values raise ValueError.
    """
    if not 0 <= semantic_weight <= 1:
        raise ValueError("semantic_weight must be between 0 and 1.")
    overall = normalize_component_score(overall_score)
    semantic = normalize_component_score(semantic_similarity)
    if overall is None or semantic is None:
        return None
    return round((1 - semantic_weight) * overall + semantic_weight * semantic, 2)


def normalize_ats_score_record(record: Mapping[str, Any], *, semantic_weight: float = 0.20) -> dict[str, Any]:
    """Return original identifiers/fields plus normalized component and review scores."""
    if not isinstance(record, Mapping):
        raise TypeError("ATS score record must be an object.")
    result = dict(record)
    for field in SCORE_COMPONENTS:
        if field in record:
            result[f"normalized_{field}"] = normalize_component_score(record[field])
    result["semantic_aware_review_score"] = calculate_semantic_aware_review_score(
        record.get("overall_score"), record.get("semantic_similarity"), semantic_weight=semantic_weight
    )
    result["review_score_method"] = {
        "formula": "(1 - semantic_weight) * overall_score + semantic_weight * semantic_similarity",
        "semantic_weight": semantic_weight,
        "note": "Experimental review aid; validate before any hiring use. Original ATS score is preserved.",
    }
    return result
