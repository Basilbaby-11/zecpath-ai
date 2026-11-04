"""Shared component-generation pipeline used by live API and batch ATS scoring."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_candidate_score(
    *, candidate_id: str, job_id: str, resume_profile: dict[str, Any],
    job: dict[str, Any], job_description: str = "", resume_text: str = "",
    semantic_result: dict[str, Any] | None = None,
    weight_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate the same four ATS components and weighted result for any workflow.

    ``resume_profile`` uses the repository's combined-resume/API profile schema;
    ``job`` uses the parsed-JD schema. Missing evidence remains missing.
    """
    from ats_engine.matcher import calculate_match_score
    from ats_engine.experience_relevance_engine import score_experience_relevance
    from ats_engine.education_relevance_engine import score_education_relevance
    from ats_engine.semantic_matching_engine import SemanticMatchingEngine
    from scoring.ats_scoring_engine import load_weight_config, score_candidate

    skills = resume_profile.get("skills") or []
    if skills and isinstance(skills[0], dict):
        candidate_skill_names = [str(x.get("name", "")) for x in skills if x.get("name")]
    else:
        candidate_skill_names = [str(x) for x in skills if str(x).strip()]
    if not candidate_skill_names and resume_text:
        from parsers.skill_ner import extract_skill_entities
        candidate_skill_names = [x.get("name", "") for x in extract_skill_entities(resume_text) if x.get("name")]

    jd_skills = [str(x.get("name", "")) for x in job.get("skills", [])
                 if isinstance(x, dict) and x.get("name")]
    skill_score = calculate_match_score(jd_skills, candidate_skill_names) if jd_skills else None

    experiences = resume_profile.get("experience") or resume_profile.get("experiences") or []
    if not experiences and resume_text:
        from parsers.experience_parser import parse_experience
        parsed_exp = parse_experience(resume_text, candidate_id=candidate_id)
        experiences = parsed_exp.get("experiences", parsed_exp.get("experience", []))
    exp_target = {
        "title": job.get("title"), "required_skills": jd_skills,
        "responsibilities": job.get("responsibilities", []),
        "description": job.get("summary") or job_description,
        # Used only by the experience relevance engine for its range assessment.
        # Skill, education, and semantic component inputs remain unchanged.
        "experience_requirements": job.get("experience_requirements") or {},
    }
    exp_result = score_experience_relevance(experiences, exp_target)
    experience_score = exp_result.get("overall_relevance_score") if experiences else None

    education = resume_profile.get("education") or []
    certifications = resume_profile.get("certifications") or []
    if (not education and not certifications) and resume_text:
        from parsers.education_certification_parser import parse_education_and_certifications
        parsed_edu = parse_education_and_certifications(resume_text)
        education, certifications = parsed_edu.get("education", []), parsed_edu.get("certifications", [])
    edu_requirements = job.get("education_requirements") or []
    cert_requirements = job.get("certification_requirements") or []
    required_fields, required_degrees = [], []
    for item in edu_requirements:
        if not isinstance(item, dict):
            continue
        field = item.get("field_of_study") or item.get("field") or item.get("name")
        if isinstance(field, list):
            required_fields.extend(str(x) for x in field if str(x).strip())
        elif field:
            required_fields.append(str(field))
        degree = item.get("qualification") or item.get("degree")
        if degree:
            required_degrees.append(str(degree))
    required_certs = [x if isinstance(x, str) else str(x.get("name") or x.get("qualification") or "")
                      for x in cert_requirements if isinstance(x, (str, dict))]
    edu_profile = {
        "required_degree": required_degrees[0] if required_degrees else "",
        "required_fields": required_fields,
        "required_certifications": [x for x in required_certs if x],
        "relevant_keywords": [],
    }
    edu_result = score_education_relevance(education, certifications, edu_profile)
    education_score = edu_result.get("overall_relevance_score")
    if not required_degrees and not required_fields and not required_certs:
        education_score = None

    if semantic_result is None:
        semantic_result = None
        try:
            semantic_resume = {
                "candidate_id": candidate_id, "skills": candidate_skill_names,
                "experience": experiences, "project_descriptions": [],
                "professional_summary": resume_text[:2500],
            }
            semantic_jd = {
                "job_id": job_id, "title": job.get("title"),
                "description": job_description or job.get("summary", ""),
                "skills": job.get("skills", []),
                "responsibilities": job.get("responsibilities", []),
            }
            semantic_result = SemanticMatchingEngine().compare(
                semantic_resume, semantic_jd, resume_id=candidate_id, job_id=job_id
            )
        except Exception as exc:  # semantic model can be optional in a partial-data run
            logger.warning("Semantic matching unavailable for %s/%s: %s", candidate_id, job_id, exc)
    semantic_section = (semantic_result or {}).get("similarity_scores", {}).get("overall", {})
    if semantic_section.get("status") == "scored" and semantic_section.get("score") is not None:
        semantic_score = round(float(semantic_section["score"]) * 100, 2)
    elif (semantic_result or {}).get("overall_score") is not None:
        semantic_score = round(float(semantic_result["overall_score"]) * 100, 2)
    else:
        semantic_score = None

    components = {
        "skill_match": skill_score,
        "experience_relevance": experience_score,
        "education_alignment": education_score,
        "semantic_similarity": semantic_score,
    }
    if weight_config is None:
        config_path = Path("config/ats_scoring_weights.json")
        weight_config = load_weight_config(config_path) if config_path.is_file() else load_weight_config()
    weighted = score_candidate(components, candidate_id=candidate_id, job_id=job_id,
                               role=job.get("title"), weight_config=weight_config)
    return {
        **weighted, "components": components,
        "evidence": {
            "matched_skills": sorted(set(x.casefold() for x in candidate_skill_names)
                                      & set(x.casefold() for x in jd_skills)),
            "required_skills": jd_skills, "candidate_skills": candidate_skill_names,
            "experience": exp_result, "education": edu_result, "semantic": semantic_result,
        },
        "scoring_source": "generated_from_uploaded_resume_and_saved_job_description",
        "human_review_required": True,
    }
