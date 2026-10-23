"""Explainable, configurable ATS candidate scoring.

Scores are decision-support signals, not hiring decisions or calibrated probabilities.
All component scores use a 0-100 scale. Missing components are excluded and the
remaining configured weights are renormalized; missing values are never silently
treated as zero.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ENGINE_VERSION = "1.0.0"

DEFAULT_WEIGHTS: dict[str, float] = {
    "skill_match": 0.35,
    "experience_relevance": 0.25,
    "education_alignment": 0.15,
    "semantic_similarity": 0.25,
}

ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "AI Engineer": {
        "skill_match": 0.40,
        "experience_relevance": 0.20,
        "education_alignment": 0.15,
        "semantic_similarity": 0.25,
    },
    "Python Developer": {
        "skill_match": 0.35,
        "experience_relevance": 0.30,
        "education_alignment": 0.10,
        "semantic_similarity": 0.25,
    },
}


def load_weight_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load role-specific weights from JSON, or use built-in defaults."""
    if path is None:
        return {"default": DEFAULT_WEIGHTS, "roles": ROLE_WEIGHTS}
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        raise ValueError("Weight configuration must be a JSON object.")
    if "default" not in config:
        raise ValueError("Weight configuration must include a 'default' object.")
    return config


def _validate_weights(weights: Mapping[str, Any]) -> dict[str, float]:
    if not weights:
        raise ValueError("At least one scoring weight is required.")
    normalized: dict[str, float] = {}
    for name, value in weights.items():
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Weight for {name!r} must be numeric.") from exc
        if weight < 0:
            raise ValueError(f"Weight for {name!r} cannot be negative.")
        normalized[str(name)] = weight
    total = sum(normalized.values())
    if total <= 0:
        raise ValueError("Scoring weights must sum to a value greater than zero.")
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Scoring weights must sum to 1.0; got {total:.6f}.")
    return normalized


def _extract_score(value: Any) -> float | None:
    """Accept a numeric score or common engine result objects."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in ("score", "overall_score", "overall_relevance_score",
                    "education_relevance_score", "relevance_score"):
            if key in value:
                return _extract_score(value[key])
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid component scores.")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid component score: {value!r}") from exc
    if not 0.0 <= score <= 100.0:
        raise ValueError(f"Component scores must be between 0 and 100; got {score}.")
    return score


def _select_weights(role: str | None, config: Mapping[str, Any] | None) -> tuple[dict[str, float], str]:
    config = config or {"default": DEFAULT_WEIGHTS, "roles": ROLE_WEIGHTS}
    defaults = config.get("default", DEFAULT_WEIGHTS)
    role_map = config.get("roles", {})
    role_key = (role or "").strip().casefold()
    matched_role = next(
        (key for key in role_map if str(key).strip().casefold() == role_key),
        None,
    )
    chosen = role_map[matched_role] if matched_role else defaults
    return _validate_weights(chosen), (str(matched_role) if matched_role else "default")


def score_candidate(
    component_scores: Mapping[str, Any],
    *,
    candidate_id: str | None = None,
    job_id: str | None = None,
    role: str | None = None,
    weight_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate a weighted ATS score and return an auditable breakdown.

    ``component_scores`` keys: skill_match, experience_relevance,
    education_alignment, semantic_similarity. Values can be 0-100 numbers or
    dictionaries containing a score field.
    """
    weights, weight_profile = _select_weights(role, weight_config)
    parsed: dict[str, float] = {}
    missing: list[str] = []
    for component in weights:
        score = _extract_score(component_scores.get(component))
        if score is None:
            missing.append(component)
        else:
            parsed[component] = score

    available_weight = sum(weights[name] for name in parsed)
    if not parsed or available_weight <= 0:
        overall: float | None = None
        category = "insufficient_data"
    else:
        overall = round(
            sum(parsed[name] * weights[name] for name in parsed) / available_weight,
            2,
        )
        category = (
            "strong_match" if overall >= 75
            else "moderate_match" if overall >= 50
            else "low_match"
        )

    breakdown: dict[str, Any] = {}
    explanations: list[str] = []
    for component, weight in weights.items():
        score = parsed.get(component)
        if score is None:
            breakdown[component] = {
                "score": None,
                "configured_weight": weight,
                "effective_weight": 0.0,
                "weighted_score": None,
                "status": "missing",
            }
            explanations.append(
                f"{component.replace('_', ' ').title()} was not scored because input data was missing."
            )
        else:
            effective_weight = weight / available_weight if available_weight else 0.0
            weighted_score = round(score * effective_weight, 2)
            breakdown[component] = {
                "score": round(score, 2),
                "configured_weight": weight,
                "effective_weight": round(effective_weight, 6),
                "weighted_score": weighted_score,
                "status": "included",
            }
            explanations.append(
                f"{component.replace('_', ' ').title()} scored {score:.2f}/100 "
                f"and contributed {weighted_score:.2f} points after weight normalization."
            )

    coverage = round(100 * available_weight, 2)
    data_quality = "complete" if not missing else ("insufficient" if not parsed else "partial")
    return {
        "engine_version": ENGINE_VERSION,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "role": role,
        "overall_score": overall,
        "category": category,
        "missing_components": missing,
        "data_quality": data_quality,

    }


def score_from_engine_outputs(
    *,
    candidate_id: str | None,
    job_id: str | None,
    role: str | None,
    skill_output: Any = None,
    experience_output: Any = None,
    education_output: Any = None,
    semantic_output: Any = None,
    weight_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Adapt common outputs from the existing Zecpath engines to the scorer."""
    def first_present(obj: Any, keys: tuple[str, ...]) -> Any:
        if not isinstance(obj, Mapping):
            return obj
        for key in keys:
            if key in obj:
                return obj[key]
        return None

    skill = first_present(skill_output, ("skill_match_score", "score", "overall_score"))
    if skill is None and isinstance(skill_output, Mapping):
        skill = first_present(skill_output.get("similarity_scores"), ("skills",))
    experience = first_present(
        experience_output, ("overall_relevance_score", "experience_relevance_score", "score")
    )
    education = first_present(
        education_output, ("overall_relevance_score", "education_relevance_score", "score")
    )
    semantic = first_present(semantic_output, ("overall_score", "semantic_similarity_score", "score"))
    if semantic is None and isinstance(semantic_output, Mapping):
        semantic = first_present(semantic_output.get("similarity_scores"), ("overall", "semantic_similarity"))

    def engine_score_to_percent(value: Any) -> Any:
        # Several upstream similarity engines emit fractions (0.0-1.0), while
        # the ATS scorer contract is consistently 0-100. Convert only adapter inputs.
        if isinstance(value, Mapping):
            copied = dict(value)
            for key in ("score", "overall_score", "overall_relevance_score",
                        "education_relevance_score", "relevance_score"):
                if key in copied:
                    copied[key] = engine_score_to_percent(copied[key])
                    return copied
            return copied
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
            return float(value) * 100
        return value

    return score_candidate(
        {
            "skill_match": engine_score_to_percent(skill),
            "experience_relevance": engine_score_to_percent(experience),
            "education_alignment": engine_score_to_percent(education),
            "semantic_similarity": engine_score_to_percent(semantic),
        },
        candidate_id=candidate_id,
        job_id=job_id,
        role=role,
        weight_config=weight_config,
    )
