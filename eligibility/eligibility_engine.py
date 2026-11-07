"""Explainable eligibility decisions built on existing ATS outputs.

This module does not calculate or alter ATS scores. It evaluates recruiter-defined
job requirements and returns eligible, review, or rejected with rule-level evidence.
Missing evidence is routed to review rather than treated as a failed requirement.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

ENGINE_VERSION = "1.0.0"
VALID_STATUSES = {"eligible", "review", "rejected"}
DEFAULT_RULES: dict[str, Any] = {
    "minimum_ats_score": 70.0,
    "review_ats_score": 55.0,
    "mandatory_skills": [],
    "use_job_required_skills": True,
    "minimum_experience_months": None,
    "maximum_experience_months": None,
    "allowed_locations": [],
    "require_location_match": False,
    "required_availability": None,
}


def load_eligibility_rules(path: str | Path | None = None) -> dict[str, Any]:
    """Load eligibility rules JSON. Defaults are used when no path is supplied."""
    if path is None:
        return {"default": dict(DEFAULT_RULES), "roles": {}, "job_overrides": {}}
    with Path(path).open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict) or not isinstance(config.get("default"), dict):
        raise ValueError("Eligibility configuration must contain a 'default' object.")
    return config


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _skill_names(values: Any) -> set[str]:
    if not isinstance(values, (list, tuple, set)):
        return set()
    names: set[str] = set()
    for value in values:
        if isinstance(value, Mapping):
            value = value.get("name") or value.get("skill")
        normalized = _normalise_text(value)
        if normalized:
            names.add(normalized)
    return names


def _select_rules(job: Mapping[str, Any], config: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    cfg = config or {"default": DEFAULT_RULES, "roles": {}, "job_overrides": {}}
    if not isinstance(cfg.get("default", DEFAULT_RULES), Mapping):
        raise ValueError("The default eligibility rules must be an object.")
    selected = dict(DEFAULT_RULES)
    selected.update(dict(cfg.get("default", {})))
    role = _normalise_text(job.get("title") or job.get("role"))
    role_rules = cfg.get("roles", {})
    role_key = next((k for k in role_rules if _normalise_text(k) == role), None) if isinstance(role_rules, Mapping) else None
    if role_key is not None:
        selected.update(dict(role_rules[role_key]))
    job_id = str(job.get("job_id") or "")
    overrides = cfg.get("job_overrides", {})
    if isinstance(overrides, Mapping) and isinstance(overrides.get(job_id), Mapping):
        selected.update(dict(overrides[job_id]))
    return validate_rules(selected), (f"job:{job_id}" if job_id and isinstance(overrides, Mapping) and job_id in overrides else f"role:{role_key}" if role_key else "default")


def validate_rules(rules: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(rules)
    for key in ("minimum_ats_score", "review_ats_score"):
        value = result.get(key)
        if isinstance(value, bool):
            raise ValueError(f"{key} must be numeric.")
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be numeric.") from exc
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be between 0 and 100.")
        result[key] = value
    if result["review_ats_score"] > result["minimum_ats_score"]:
        raise ValueError("review_ats_score must be <= minimum_ats_score.")
    for key in ("minimum_experience_months", "maximum_experience_months"):
        value = result.get(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{key} must be a non-negative integer or null.")
    low, high = result.get("minimum_experience_months"), result.get("maximum_experience_months")
    if low is not None and high is not None and low > high:
        raise ValueError("minimum_experience_months cannot exceed maximum_experience_months.")
    for key in ("mandatory_skills", "allowed_locations"):
        if not isinstance(result.get(key, []), list):
            raise ValueError(f"{key} must be a list.")
    if not isinstance(result.get("use_job_required_skills", True), bool):
        raise ValueError("use_job_required_skills must be a boolean.")
    if not isinstance(result.get("require_location_match", False), bool):
        raise ValueError("require_location_match must be a boolean.")
    return result


def evaluate_eligibility(
    *, candidate: Mapping[str, Any], ats_result: Mapping[str, Any] | None,
    job: Mapping[str, Any], rules_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate ATS score, required skills, experience, location and availability.

    Explicit unmet requirements cause rejection. Missing/ambiguous evidence causes
    review. A candidate is eligible only when every configured check passes.
    """
    if not isinstance(candidate, Mapping) or not isinstance(job, Mapping):
        raise TypeError("candidate and job must be mappings.")
    score_data = ats_result or {}
    rules, rules_source = _select_rules(job, rules_config)
    checks: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    unknowns: list[str] = []

    def record(name: str, status: str, message: str, **details: Any) -> None:
        checks.append({"rule": name, "status": status, "message": message, **details})
        if status == "failed":
            hard_failures.append(name)
        elif status == "unknown":
            unknowns.append(name)

    score = score_data.get("overall_score")
    if score is None or score_data.get("data_quality") in {"partial", "insufficient"} or score_data.get("missing_components"):
        record(
            "ats_score", "unknown",
            "ATS score is missing or based on incomplete scoring data; recruiter review is required.",
            value=score,
            data_quality=score_data.get("data_quality"),
            missing_components=score_data.get("missing_components") or [],
        )
    else:
        if isinstance(score, bool):
            raise ValueError("ATS overall_score must be numeric or null.")
        try:
            score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError("ATS overall_score must be numeric or null.") from exc
        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError("ATS overall_score must be between 0 and 100.")
        if score >= rules["minimum_ats_score"]:
            record("ats_score", "passed", "ATS score meets the eligibility cutoff.", value=round(score, 2), threshold=rules["minimum_ats_score"])
        elif score >= rules["review_ats_score"]:
            record("ats_score", "unknown", "ATS score falls in the recruiter-review band.", value=round(score, 2), threshold=rules["minimum_ats_score"], review_threshold=rules["review_ats_score"])
        else:
            record("ats_score", "failed", "ATS score is below the configured review threshold.", value=round(score, 2), threshold=rules["review_ats_score"])

    # Deduplicate required skills case-insensitively while preserving readable labels.
    required_by_key: dict[str, str] = {}
    for raw_skill in rules.get("mandatory_skills", []):
        label = raw_skill.get("name") or raw_skill.get("skill") if isinstance(raw_skill, Mapping) else raw_skill
        key = _normalise_text(label)
        if key:
            required_by_key.setdefault(key, str(label).strip())

    if rules.get("use_job_required_skills", True):
        for item in job.get("skills", []) or []:
            if isinstance(item, Mapping):
                requirement_type = _normalise_text(
                    item.get("requirement_type") or item.get("type") or item.get("category") or "required"
                )
                # Explicit optional/preferred labels must never become hard requirements.
                is_required = item.get("is_required", item.get("required", None))
                if is_required is False or requirement_type in {
                    "preferred", "optional", "nice to have", "nice-to-have",
                    "desirable", "bonus", "good to have"
                }:
                    continue
                name = item.get("name") or item.get("skill")
            else:
                # Legacy parsed-JD schemas represent plain skill strings as required.
                name = item
            key = _normalise_text(name)
            if key:
                required_by_key.setdefault(key, str(name).strip())

    required_skills = list(required_by_key.values())
    candidate_skills = _skill_names(candidate.get("skills"))
    if required_skills:
        if not candidate_skills:
            record("mandatory_skills", "unknown", "Candidate skill evidence is unavailable or empty.", required=required_skills, missing=[])
        else:
            missing = [label for key, label in required_by_key.items() if key not in candidate_skills]
            if missing:
                record("mandatory_skills", "failed", "One or more mandatory skills were not found in the candidate profile.", required=required_skills, missing=missing)
            else:
                record("mandatory_skills", "passed", "All configured mandatory skills were found.", required=required_skills, matched=required_skills)
    else:
        record("mandatory_skills", "passed", "No mandatory skills are configured.", required=[])

    min_months = rules.get("minimum_experience_months")
    max_months = rules.get("maximum_experience_months")
    if min_months is not None or max_months is not None:
        months = candidate.get("total_experience_months")
        if months is None:
            record("experience_range", "unknown", "Verified total experience in months is unavailable.", minimum_months=min_months, maximum_months=max_months)
        elif isinstance(months, bool) or not isinstance(months, (int, float)) or months < 0:
            raise ValueError("total_experience_months must be a non-negative number or null.")
        elif min_months is not None and months < min_months:
            record("experience_range", "failed", "Candidate experience is below the minimum requirement.", actual_months=months, minimum_months=min_months, maximum_months=max_months)
        elif max_months is not None and months > max_months:
            record("experience_range", "failed", "Candidate experience exceeds the configured maximum range.", actual_months=months, minimum_months=min_months, maximum_months=max_months)
        else:
            record("experience_range", "passed", "Candidate experience is within the configured range.", actual_months=months, minimum_months=min_months, maximum_months=max_months)
    else:
        record("experience_range", "passed", "No experience range is configured.")

    allowed_locations = [_normalise_text(x) for x in rules.get("allowed_locations", []) if _normalise_text(x)]
    require_location = rules.get("require_location_match", False) or bool(allowed_locations)
    if require_location:
        location = candidate.get("location")
        if isinstance(location, Mapping):
            location_text = _normalise_text(" ".join(str(v) for v in location.values() if v))
        else:
            location_text = _normalise_text(location)
        if not location_text:
            record("location", "unknown", "Candidate location is unavailable; recruiter review is required.", allowed_locations=allowed_locations)
        elif allowed_locations and not any(loc in location_text for loc in allowed_locations):
            record("location", "failed", "Candidate location does not match the configured locations.", candidate_location=location_text, allowed_locations=allowed_locations)
        else:
            record("location", "passed", "Candidate location satisfies the configured location rule.", candidate_location=location_text, allowed_locations=allowed_locations)
    else:
        record("location", "passed", "No location restriction is configured.")

    required_availability = rules.get("required_availability")
    if required_availability:
        availability = candidate.get("availability")
        if availability is None or not _normalise_text(availability):
            record("availability", "unknown", "Candidate availability is unavailable; recruiter review is required.", required=required_availability)
        elif _normalise_text(availability) != _normalise_text(required_availability):
            record("availability", "failed", "Candidate availability does not meet the configured requirement.", candidate_availability=availability, required=required_availability)
        else:
            record("availability", "passed", "Candidate availability meets the configured requirement.", candidate_availability=availability, required=required_availability)
    else:
        record("availability", "passed", "No availability restriction is configured.")

    status = "rejected" if hard_failures else "review" if unknowns else "eligible"
    return {
        "engine_version": ENGINE_VERSION,
        "candidate_id": candidate.get("candidate_id") or score_data.get("candidate_id"),
        "job_id": job.get("job_id") or score_data.get("job_id"),
        "status": status,
        "eligible_for_ai_screening": status == "eligible",
        "decision_reason": (
            "One or more explicit eligibility requirements were not met." if hard_failures
            else "One or more required data points need recruiter verification." if unknowns
            else "All configured eligibility requirements were satisfied."
        ),
        "failed_rules": hard_failures,
        "review_rules": unknowns,
        "rules_source": rules_source,
        "rules_applied": rules,
        "ats_score": score,
        "checks": checks,
        "human_review_required": status != "eligible",
    }
