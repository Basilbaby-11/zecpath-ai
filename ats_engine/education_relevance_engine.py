"""Explainable baseline relevance scoring for education and certifications."""
from __future__ import annotations

import re
from typing import Any, Iterable

DEGREE_LEVELS = {
    "secondary school certificate": 1, "higher secondary certificate": 2,
    "diploma": 2, "associate degree": 2, "bachelor of science": 3,
    "bachelor of commerce": 3, "bachelor of computer applications": 3,
    "bachelor of engineering": 3, "bachelor of technology": 3,
    "b.tech": 3, "btech": 3, "b.e.": 3, "be": 3, "b.sc": 3, "bsc": 3,
    "bachelor's degree": 3, "bachelors degree": 3, "bachelor degree": 3,
    "master of science": 4, "master of computer applications": 4,
    "master of engineering": 4, "master of technology": 4,
    "master of business administration": 4, "doctor of philosophy": 5,
}

FIELD_GROUPS = {
    "artificial intelligence": {"artificial intelligence", "ai", "machine learning", "deep learning", "data science", "nlp"},
    "computer science": {"computer science", "computer science and engineering", "cse", "information technology", "it", "software engineering", "computer applications"},
    "data analytics": {"data analytics", "data analysis", "business intelligence", "statistics", "data science"},
    "engineering": {"engineering", "electrical", "electronics", "mechanical", "civil"},
    "business": {"business", "business administration", "commerce", "management", "finance", "accounting"},
    "cybersecurity": {"cybersecurity", "information security", "network security"},
    "cloud computing": {"cloud", "aws", "azure", "google cloud", "devops"},
}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]+", value.lower()))


def _contains_related_field(field: str, required_fields: Iterable[str]) -> tuple[bool, list[str]]:
    field_norm = field.lower().strip()
    matched = []
    for required in required_fields:
        req = required.lower().strip()
        if not req:
            continue
        if req in field_norm or field_norm in req:
            matched.append(required)
            continue
        for group, members in FIELD_GROUPS.items():
            if any(member in field_norm for member in members) and any(member in req for member in members):
                matched.append(required)
                break
    return bool(matched), matched


def _degree_level(value: str) -> int:
    """Normalize common degree abbreviations to a comparable level."""
    q = re.sub(r"\s+", " ", value.lower().strip())
    aliases = {
        "b.tech": "bachelor of technology", "btech": "bachelor of technology",
        "b.e.": "bachelor of engineering", "be": "bachelor of engineering",
        "b.sc": "bachelor of science", "bsc": "bachelor of science",
        "bca": "bachelor of computer applications", "bachelor's degree": "bachelor's degree",
        "bachelors degree": "bachelor's degree", "bachelor degree": "bachelor's degree",
        "m.tech": "master of technology", "mtech": "master of technology",
        "m.sc": "master of science", "msc": "master of science",
    }
    q = aliases.get(q, q)
    return DEGREE_LEVELS.get(q, 3 if q in {"bachelor's degree", "bachelor degree"} else 0)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [str(v) for v in value.values() if v]
    return [str(v) for v in value if v]


def score_education_relevance(education: list[dict[str, Any]] | None = None,
                              certifications: list[dict[str, Any]] | None = None,
                              job_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score education/certification relevance from 0–100 with transparent evidence.

    job_profile supports ``required_degree``, ``required_fields``,
    ``preferred_fields``, ``required_certifications`` and ``relevant_keywords``.
    Scores are heuristics, not calibrated probabilities or hiring decisions.
    """
    education = education or []
    certifications = certifications or []
    job_profile = job_profile or {}
    # Accept both the compact profile used by the engine and the parsed JD schema.
    requirements = job_profile.get("education_requirements") or []
    required_degree = str(job_profile.get("required_degree") or "").strip().lower()
    required_fields = _as_list(job_profile.get("required_fields"))
    preferred_fields = _as_list(job_profile.get("preferred_fields"))
    if requirements:
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            qualification = str(requirement.get("qualification") or "").strip()
            if qualification and not required_degree:
                required_degree = qualification.lower()
            fields = _as_list(requirement.get("field_of_study"))
            if requirement.get("mandatory"):
                required_fields.extend(fields)
            else:
                preferred_fields.extend(fields)
    required_certs = [str(x).strip().lower() for x in _as_list(job_profile.get("required_certifications")) if str(x).strip()]
    keywords = [str(x).strip().lower() for x in _as_list(job_profile.get("relevant_keywords")) if str(x).strip()]

    edu_best = 0.0
    edu_evidence: list[str] = []
    for item in education:
        qualification = str(item.get("qualification") or "").lower()
        field_value = item.get("field_of_study") or ""
        field = ", ".join(_as_list(field_value)) if not isinstance(field_value, str) else field_value
        field_match, fields_matched = _contains_related_field(field, [*required_fields, *preferred_fields])
        qualification_norm = re.sub(r"\s+", " ", qualification.strip().lower())
        required_level = _degree_level(required_degree) if required_degree else 0
        candidate_level = _degree_level(qualification_norm)
        # A bachelor's-level qualification (including B.Tech/B.E.) satisfies a
        # generic bachelor's requirement; higher degrees satisfy lower levels.
        degree_match = bool(required_level and candidate_level >= required_level)
        degree_level = candidate_level
        score = (55 if field_match else 0) + (30 if degree_match else (15 if degree_level >= 3 else 0))
        if item.get("end_year"):
            score += 5
        if item.get("institution"):
            score += 5
        score = min(score, 90)
        if score > edu_best:
            edu_best = score
            edu_evidence = [f"Qualification: {item.get('qualification') or 'not stated'}"]
            if field:
                edu_evidence.append(f"Field of study: {field}")
            if fields_matched:
                edu_evidence.append("Related job field(s): " + ", ".join(fields_matched))
            if degree_match:
                edu_evidence.append("Required degree type matched")

    cert_names = [str(item.get("name") or "") for item in certifications]
    cert_text = " ".join(cert_names).lower()
    cert_matches = [req for req in required_certs if req in cert_text or any(req in name.lower() for name in cert_names)]
    keyword_matches = [kw for kw in keywords if kw in cert_text]
    cert_score = min(100.0, (70.0 * len(cert_matches) / len(required_certs) if required_certs else 0.0) + min(30.0, 10.0 * len(keyword_matches)))
    if not required_certs and not keywords and certifications:
        cert_score = min(60.0, 20.0 * len(certifications))

    # When only one dimension is specified, avoid penalizing the missing dimension.
    has_education_requirements = bool(required_degree or required_fields or preferred_fields)
    has_cert_requirements = bool(required_certs or keywords)
    if has_education_requirements and has_cert_requirements:
        overall = round(0.7 * edu_best + 0.3 * cert_score, 2)
    elif has_education_requirements:
        overall = round(edu_best, 2)
    elif has_cert_requirements:
        overall = round(cert_score, 2)
    else:
        overall = round(max(edu_best, cert_score), 2)
    return {
        "education_relevance_score": round(edu_best, 2),
        "certification_relevance_score": round(cert_score, 2),
        "overall_relevance_score": overall,
        "matched_required_certifications": cert_matches,
        "matched_relevant_keywords": keyword_matches,
        "education_evidence": edu_evidence,
        "certification_evidence": [f"Matched certification: {x}" for x in cert_matches] + [f"Matched keyword: {x}" for x in keyword_matches],
        "scoring_note": "Heuristic decision-support score; verify extracted credentials and review candidates fairly.",
    }
