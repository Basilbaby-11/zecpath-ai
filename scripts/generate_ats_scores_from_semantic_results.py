"""Generate Day 13 ATS scores from Zecpath semantic results and combined resumes.

The semantic engine returns normalized scores in [0, 1]. This script converts
those values to [0, 100] before calling the ATS scorer.

Mappings:
- similarity_scores.skills.score -> skill_match (semantic section proxy)
- similarity_scores.experience.score -> experience_relevance (semantic section proxy)
- similarity_scores.overall.score -> semantic_similarity
- education_alignment -> calculated using education_relevance_engine.py and the parsed JD

Run the script like this (Windows PowerShell example):

python scripts/generate_ats_scores_from_semantic_results.py `
>>   --semantic-results data\semantic_matching_outputs\semantic_matching_results.json `
>>   --combined-resumes data\combined_resume_outputs\all_resumes_combined.json `
>>   --parsed-jds data\parsed_job_descriptions\all_parsed_job_descriptions.json `
>>   --weights config\ats_scoring_weights.json `
>>   --output data\ats_scores\ats_scoring_results.json

Note: section similarities are proxies, not independent deterministic skill or
experience relevance scores. Education scoring is heuristic decision support.
Missing components are marked and remaining weights are renormalized.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.ats_scoring_engine import load_weight_config, score_candidate
from ats_engine.education_relevance_engine import score_education_relevance


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def to_percent(value: Any) -> float | None:
    """Convert normalized 0-1 similarity to 0-100; preserve missing values."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean similarity values are invalid.")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"Expected normalized semantic score in [0, 1], got {number}.")
    return round(number * 100.0, 2)


def get_score(result: dict[str, Any], section: str) -> float | None:
    section_data = result.get("similarity_scores", {}).get(section, {})
    if not isinstance(section_data, dict) or section_data.get("status") == "insufficient_data":
        return None
    return to_percent(section_data.get("score"))


def derive_role(job_id: str | None) -> str | None:
    if not job_id:
        return None
    slug = re.sub(r"^job_jd_\d+_", "", job_id)
    slug = re.sub(r"_[0-9a-f]{8,}$", "", slug)
    slug = re.sub(r"^sample-", "", slug)
    return slug.replace("_", " ").strip().title() or None



def _degree_keyword(qualification: str) -> str:
    """Normalize a parsed qualification to a degree keyword."""
    value = re.sub(r"[^a-z ]", " ", str(qualification or "").lower())
    value = re.sub(r"\\s+", " ", value).strip()
    for keyword in ("doctor", "phd", "master", "bachelor", "diploma", "associate", "secondary"):
        if keyword in value:
            return keyword
    return value


def education_score_for_pair(resume: dict[str, Any], job: dict[str, Any] | None) -> float | None:
    """Calculate education/certification relevance, or None if the JD has no requirements."""
    if not isinstance(job, dict):
        return None
    education_requirements = job.get("education_requirements") or []
    certification_requirements = job.get("certification_requirements") or []
    if not education_requirements and not certification_requirements:
        return None

    degrees: list[str] = []
    fields: list[str] = []
    for requirement in education_requirements:
        if not isinstance(requirement, dict):
            continue
        degree = _degree_keyword(requirement.get("qualification", ""))
        if degree:
            degrees.append(degree)
        field_values = requirement.get("field_of_study") or []
        if isinstance(field_values, str):
            field_values = [field_values]
        fields.extend(str(item) for item in field_values if str(item).strip())

    certs: list[str] = []
    for requirement in certification_requirements:
        if isinstance(requirement, str):
            certs.append(requirement)
        elif isinstance(requirement, dict):
            name = requirement.get("name") or requirement.get("qualification") or requirement.get("title")
            if name:
                certs.append(str(name))

    education = resume.get("education") or []
    certifications = resume.get("certifications") or []

    # Evaluate multiple alternative degree requirements independently and use the
    # best education score, so "Bachelor's degree OR Diploma" isn't penalized.
    if len(set(degrees)) > 1:
        degree_scores = []
        for degree in dict.fromkeys(degrees):
            profile = {"required_degree": degree, "required_fields": fields}
            scored = score_education_relevance(education, certifications, profile)
            degree_scores.append(float(scored.get("education_relevance_score") or 0.0))
        edu_score = max(degree_scores, default=0.0)
        if certs:
            cert_result = score_education_relevance(
                education, certifications, {"required_certifications": certs}
            )
            cert_score = float(cert_result.get("certification_relevance_score") or 0.0)
            return round(0.7 * edu_score + 0.3 * cert_score, 2)
        return round(edu_score, 2)

    profile: dict[str, Any] = {}
    if degrees:
        profile["required_degree"] = degrees[0]
    if fields:
        profile["required_fields"] = list(dict.fromkeys(fields))
    if certs:
        profile["required_certifications"] = list(dict.fromkeys(certs))

    scored = score_education_relevance(education, certifications, profile)
    value = scored.get("overall_relevance_score")
    return round(float(value), 2) if value is not None else None


def generate(
    semantic_results: dict[str, Any],
    combined_resumes: dict[str, Any],
    weight_config: dict[str, Any] | None = None,
    parsed_job_descriptions: Any = None,
) -> dict[str, Any]:
    """Generate one ATS score per semantic result pair."""
    resume_ids = {
        resume.get("candidate_id")
        for resume in combined_resumes.get("resumes", [])
        if isinstance(resume, dict)
    }
    resume_by_id = {
        resume.get("candidate_id"): resume
        for resume in combined_resumes.get("resumes", [])
        if isinstance(resume, dict) and resume.get("candidate_id")
    }
    job_records = (
        parsed_job_descriptions
        if isinstance(parsed_job_descriptions, list)
        else parsed_job_descriptions.get("jobs", parsed_job_descriptions.get("job_descriptions", []))
        if isinstance(parsed_job_descriptions, dict)
        else []
    )
    job_by_id = {
        job.get("job_id"): job
        for job in job_records
        if isinstance(job, dict) and job.get("job_id")
    }
    records = semantic_results.get("results", [])
    output: list[dict[str, Any]] = []
    skipped = 0

    for result in records:
        if not isinstance(result, dict):
            skipped += 1
            continue
        candidate_id = result.get("resume_id")
        job_id = result.get("job_id")
        if candidate_id not in resume_ids:
            skipped += 1
            continue

        section_scores = result.get("similarity_scores", {})
        skill_score = get_score(result, "skills")
        experience_score = get_score(result, "experience")
        semantic_score = get_score(result, "overall")

        scored = score_candidate(
            {
                "skill_match": skill_score,
                "experience_relevance": experience_score,
                "education_alignment": education_score_for_pair(
                    resume_by_id.get(candidate_id, {}), job_by_id.get(job_id)
                ),
                "semantic_similarity": semantic_score,
            },
            candidate_id=candidate_id,
            job_id=job_id,
            role=derive_role(job_id),
            weight_config=weight_config,
        )
        scored["component_scores"] = {
                "skill_match": {
                    "score": skill_score,
                    "status": "scored" if skill_score is not None else "missing",
                },
                "experience_relevance": {
                    "score": experience_score,
                    "status": "scored" if experience_score is not None else "missing",
                },
                "education_alignment": {
                    "score": education_score_for_pair(
                        resume_by_id.get(candidate_id, {}),
                        job_by_id.get(job_id),
                    ),
                    "status": "scored"
                    if education_score_for_pair(
                        resume_by_id.get(candidate_id, {}),
                        job_by_id.get(job_id),
                    ) is not None
                    else "missing",
                },
                "semantic_similarity": {
                    "score": semantic_score,
                    "status": "scored" if semantic_score is not None else "missing",
                },
            }
        scored["source"] = {
            "semantic_results_file": "semantic_matching_results.json",
            "combined_resume_file": "all_resumes_combined.json",
            "component_mapping": {
                "skill_match": "similarity_scores.skills.score",
                "experience_relevance": "similarity_scores.experience.score",
                "semantic_similarity": "similarity_scores.overall.score",
                "education_alignment": "education_relevance_engine + parsed job education/certification requirements",
            },
            "semantic_engine_overall_score": result.get("overall_score"),
            "semantic_engine_overall_category": result.get("overall_category"),
        }
        output.append(scored)

    output.sort(
        key=lambda row: (
            row.get("job_id") or "",
            -(row["overall_score"] if row["overall_score"] is not None else -1),
            row.get("candidate_id") or "",
        )
    )
    return {
        "engine_version": "1.0.0",
        "pipeline": "day13_ats_scoring",
        "input_semantic_pair_count": len(records),
        "generated_score_count": len(output),
        "skipped_count": skipped,
        "weight_profile_note": "Role profile is used only when the role name matches a configured role; otherwise default weights apply.",
        "score_scale": "0-100",
        "results": output,
    }


def compact_output(result: dict[str, Any]) -> dict[str, Any]:
    """Return a concise, presentation-ready ATS JSON without debug metadata."""
    compact_results = []
    for row in result.get("results", []):
        components = row.get("component_scores", {})
        compact_results.append({
            "candidate_id": row.get("candidate_id"),
            "job_id": row.get("job_id"),
            "role": row.get("role"),
            "skill_match": (components.get("skill_match") or {}).get("score"),
            "experience_relevance": (components.get("experience_relevance") or {}).get("score"),
            "education_alignment": (components.get("education_alignment") or {}).get("score"),
            "semantic_similarity": (components.get("semantic_similarity") or {}).get("score"),
            "overall_score": row.get("overall_score"),
            "category": row.get("category"),
        })
    return {
        "engine_version": result.get("engine_version", "1.0.0"),
        "pipeline": result.get("pipeline", "day13_ats_scoring"),
        "input_semantic_pair_count": result.get("input_semantic_pair_count", 0),
        "generated_score_count": result.get("generated_score_count", len(compact_results)),
        "skipped_count": result.get("skipped_count", 0),
        "score_scale": "0-100",
        "results": compact_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-results", required=True, help="Path to semantic_matching_results.json")
    parser.add_argument("--combined-resumes", required=True, help="Path to all_resumes_combined.json")
    parser.add_argument("--parsed-jds", required=True, help="Path to combined parsed job descriptions JSON")
    parser.add_argument("--weights", default="config/ats_scoring_weights.json", help="Weight config JSON")
    parser.add_argument("--output", default="data/ats_scores/ats_scoring_results.json", help="Output JSON path")
    args = parser.parse_args()

    semantic_results = read_json(args.semantic_results)
    combined_resumes = read_json(args.combined_resumes)
    parsed_jds = read_json(args.parsed_jds)
    weight_config = load_weight_config(args.weights) if args.weights else None
    result = generate(semantic_results, combined_resumes, weight_config, parsed_jds)

    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(compact_output(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Generated {result['generated_score_count']} ATS scores "
        f"(skipped {result['skipped_count']}) -> {destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
