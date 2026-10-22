"""Explainable baseline relevance scoring for education and certifications."""
from __future__ import annotations

import re
from typing import Any, Iterable

DEGREE_LEVELS = {
    "secondary school certificate": 1, "higher secondary certificate": 2,
    "diploma": 2, "associate degree": 2, "bachelor of science": 3,
    "bachelor of commerce": 3, "bachelor of computer applications": 3,
    "bachelor of engineering": 3, "bachelor of technology": 3,
    "master of science": 4, "master of computer applications": 4,
    "master of engineering": 4, "master of technology": 4,
    "master of business administration": 4, "doctor of philosophy": 5,
}

FIELD_GROUPS = {
    "artificial intelligence": {"artificial intelligence", "ai", "machine learning", "deep learning", "data science", "nlp"},
    "computer science": {"computer science", "computer science and engineering", "information technology", "software engineering", "computer applications"},
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
    required_degree = str(job_profile.get("required_degree") or "").strip().lower()
    required_fields = job_profile.get("required_fields") or []
    preferred_fields = job_profile.get("preferred_fields") or []
    required_certs = [str(x).strip().lower() for x in job_profile.get("required_certifications", []) if str(x).strip()]
    keywords = [str(x).strip().lower() for x in job_profile.get("relevant_keywords", []) if str(x).strip()]

    edu_best = 0.0
    edu_evidence: list[str] = []
    for item in education:
        qualification = str(item.get("qualification") or "").lower()
        field = str(item.get("field_of_study") or "")
        field_match, fields_matched = _contains_related_field(field, [*required_fields, *preferred_fields])
        degree_match = bool(required_degree and required_degree in qualification)
        degree_level = DEGREE_LEVELS.get(qualification, 0)
        score = (45 if field_match else 0) + (35 if degree_match else (15 if degree_level >= 3 else 0))
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
