"""Explainable experience-to-job and role-to-role similarity.

Uses TF-IDF/cosine similarity plus explicit normalized skill overlap. Scores are
ranking aids only, not hiring decisions. No external model download is required.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

SCORING_VERSION = "2.1.0-explainable-role-similarity"

# Canonicalize common spellings/abbreviations without treating broad concepts as
# interchangeable (e.g. Java is not JavaScript; NLP is not NLU).
_SKILL_ALIASES = {
    "scikit learn": "scikit-learn", "sklearn": "scikit-learn",
    "pytorch": "pytorch", "py torch": "pytorch",
    "js": "javascript", "nodejs": "node.js", "node js": "node.js",
    "postgres": "postgresql", "powerbi": "power bi",
    "ci cd": "ci/cd", "continuous integration continuous delivery": "ci/cd",
    "qa qc": "qa/qc", "quality assurance quality control": "qa/qc",
    "restful api": "rest api", "apis": "api",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value)
    return str(value)


def _normalize_phrase(value: Any) -> str:
    text = _text(value).casefold().strip()
    text = re.sub(r"[^a-z0-9+#./-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _SKILL_ALIASES.get(text, text)


def _skill_set(values: Any) -> set[str]:
    if isinstance(values, dict):
        values = list(values.values())
    if not isinstance(values, (list, tuple, set)):
        values = [values] if values else []
    return {normal for value in values if (normal := _normalize_phrase(value))}


def _similarity(a: str, b: str) -> float:
    """Return TF-IDF cosine similarity as a percentage, with safe fallback."""
    left, right = a.casefold().strip(), b.casefold().strip()
    if not left or not right:
        return 0.0
    if left == right:
        return 100.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform([left, right])
        return round(float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0]) * 100, 2)
    except (ImportError, ValueError):
        a_tokens, b_tokens = set(left.split()), set(right.split())
        return round(100 * len(a_tokens & b_tokens) / len(a_tokens | b_tokens), 2) if a_tokens | b_tokens else 0.0


def _skill_overlap(source_skills: Any, target_skills: Any) -> dict[str, Any]:
    source, target = _skill_set(source_skills), _skill_set(target_skills)
    matched = sorted(source & target)
    missing = sorted(target - source)
    extra = sorted(source - target)
    # Recall emphasizes coverage of target requirements; Jaccard prevents a very
    # large unrelated skill list from appearing perfect.
    recall = len(matched) / len(target) * 100 if target else 0.0
    jaccard = len(matched) / len(source | target) * 100 if source | target else 0.0
    score = round(0.7 * recall + 0.3 * jaccard, 2) if target else 0.0
    return {"score": score, "matched_skills": matched, "missing_target_skills": missing,
            "additional_source_skills": extra, "source_skill_count": len(source),
            "target_skill_count": len(target)}


def role_similarity(source_title: str | None, target_title: str | None,
                    source_skills: Iterable[str] | None = None,
                    target_skills: Iterable[str] | None = None) -> dict[str, Any]:
    """Compare two roles using title similarity and normalized skill overlap."""
    source, target = _text(source_title), _text(target_title)
    source_skills, target_skills = list(source_skills or []), list(target_skills or [])
    if not source.strip() or not target.strip():
        return {"score": 0.0, "relationship": "insufficient_data", "title_similarity": 0.0,
                "skill_similarity": 0.0, "matched_skills": [], "missing_target_skills": [],
                "method": "tfidf_title_plus_skill_overlap"}
    title_score = _similarity(source, target)
    overlap = _skill_overlap(source_skills, target_skills)
    has_skill_evidence = bool(_skill_set(source_skills) or _skill_set(target_skills))
    score = round(0.45 * title_score + 0.55 * overlap["score"], 2) if has_skill_evidence else title_score
    relationship = "high" if score >= 65 else "moderate" if score >= 30 else "low"
    return {"score": score, "relationship": relationship, "title_similarity": title_score,
            "skill_similarity": overlap["score"], "matched_skills": overlap["matched_skills"],
            "missing_target_skills": overlap["missing_target_skills"],
            "method": "tfidf_title_plus_normalized_skill_overlap"}


def score_experience_relevance(experiences: list[dict[str, Any]], target_job: dict[str, Any]) -> dict[str, Any]:
    """Rank roles against a job description and return score evidence per role."""
    target_title = _text(target_job.get("title") or target_job.get("job_title"))
    target_skills = target_job.get("required_skills") or target_job.get("skills") or []
    if isinstance(target_skills, dict):
        target_skills = list(target_skills.values())
    target_responsibilities = _text(target_job.get("responsibilities"))
    target_description = _text(target_job.get("description") or target_job.get("job_description"))
    target_context = " ".join([target_title, _text(target_skills), target_responsibilities, target_description]).strip()
    results = []
    for item in experiences:
        title = _text(item.get("designation") or item.get("job_title"))
        skills = item.get("skills_used", [])
        role_match = role_similarity(title, target_title, skills, target_skills)
        evidence = " ".join([title, _text(skills), _text(item.get("description")), _text(item.get("source_text"))]).strip()
        context_score = _similarity(evidence, target_context)
        skill_match = _skill_overlap(skills, target_skills)
        # Explicit skill coverage and textual evidence make the score interpretable.
        if _skill_set(target_skills):
            score = round(0.35 * role_match["title_similarity"] + 0.35 * skill_match["score"] + 0.30 * context_score, 2)
        else:
            score = round(0.45 * role_match["title_similarity"] + 0.55 * context_score, 2)
        results.append({
            "experience_id": item.get("experience_id"), "designation": title,
            "employer": item.get("employer"), "relevance_score": score,
            "relevance_level": "high" if score >= 65 else "moderate" if score >= 30 else "low",
            "title_similarity_score": role_match["title_similarity"],
            "skill_match_score": skill_match["score"],
            "context_similarity_score": context_score,
            "matched_required_skills": skill_match["matched_skills"],
            "missing_required_skills": skill_match["missing_target_skills"],
            "role_similarity": role_match,
        })
    results.sort(key=lambda row: row["relevance_score"], reverse=True)
    return {
        "target_job_title": target_title,
        "overall_relevance_score": round(sum(r["relevance_score"] for r in results) / len(results), 2) if results else 0.0,
        "experience_scores": results, "scoring_version": SCORING_VERSION,
        "method": "weighted TF-IDF cosine similarity + normalized explicit skill overlap",
        "score_interpretation": {"low": "below 30", "moderate": "30 to below 65", "high": "65 or above"},
        "decision_support_only": True,
    }
