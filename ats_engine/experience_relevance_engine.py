"""Explainable experience-to-job matching using structured and narrative evidence.

Scores are decision-support signals, not hiring decisions. Skill evidence is
extracted from both skills_used and the experience description.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

SCORING_VERSION = "2.4.0-evidence-aware-context-responsibilities"
_SKILL_ALIASES = {
    "js": "javascript", "nodejs": "node.js", "node js": "node.js",
    "postgres": "postgresql", "restful api": "rest api", "restful apis": "rest api",
    "rest apis": "rest api", "rest endpoints": "rest api", "api endpoints": "rest api", "apis": "api", "github actions": "git",
    "sql queries": "sql", "sql query": "sql", "query optimization": "sql",
    "role based access control": "authentication", "rbac": "authentication",
}
_SKILL_PATTERNS = {
    "javascript": r"\bjavascript\b|\bjs\b", "node.js": r"\bnode\.?js\b|\bnodejs\b",
    "express": r"\bexpress(?:\.js)?\b", "rest api": r"\brest(?:ful)?\s+apis?\b|\brest\s+endpoints?\b|\bapi endpoints?\b",
    "sql": r"\bsql\b|\bpostgresql queries?\b|\bmysql queries?\b|\bquery optimization\b",
    "authentication": r"\bauthentication\b|\bauthorization\b|\boauth\b|\bjwt\b|\brbac\b|role[- ]based access control",
    "docker": r"\bdocker\b", "postgresql": r"\bpostgres(?:ql)?\b", "redis": r"\bredis\b",
    "python": r"\bpython\b", "fastapi": r"\bfast\s?api\b", "flask": r"\bflask\b",
    "git": r"\bgit\b|\bgithub actions\b", "django": r"\bdjango\b",
}
_ROLE_TERMS = {
    "backend developer": {"backend", "server", "api", "software developer", "software engineer"},
    "backend engineer": {"backend", "server", "api", "software developer", "software engineer"},
}


def _text(value: Any) -> str:
    if value is None: return ""
    if isinstance(value, dict): return " ".join(_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)): return " ".join(_text(v) for v in value)
    return str(value)


def _normalize_phrase(value: Any) -> str:
    text = re.sub(r"[^a-z0-9+#./-]+", " ", _text(value).casefold()).strip()
    text = re.sub(r"\s+", " ", text)
    return _SKILL_ALIASES.get(text, text)


def _skill_set(values: Any) -> set[str]:
    if isinstance(values, dict): values = list(values.values())
    if not isinstance(values, (list, tuple, set)): values = [values] if values else []
    return {_normalize_phrase(v) for v in values if _normalize_phrase(v)}


def _skills_in_text(text: str) -> set[str]:
    found = set()
    for canonical, pattern in _SKILL_PATTERNS.items():
        if re.search(pattern, text, re.I): found.add(canonical)
    return found


def _similarity(a: str, b: str) -> float:
    left, right = a.casefold().strip(), b.casefold().strip()
    if not left or not right: return 0.0
    if left == right: return 100.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform([left, right])
        return round(float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0]) * 100, 2)
    except (ImportError, ValueError):
        a_tokens, b_tokens = set(left.split()), set(right.split())
        return round(100 * len(a_tokens & b_tokens) / len(a_tokens | b_tokens), 2) if a_tokens | b_tokens else 0.0


# Common function words are excluded from lexical evidence matching. This is a
# deterministic fallback signal, not an embedding model or a hiring probability.
_TEXT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "with", "within", "using", "used", "work", "worked",
    "responsible", "responsibilities", "experience", "including",
}


def _content_tokens(value: Any) -> set[str]:
    tokens = re.findall(r"[a-z0-9+#.]+", _text(value).casefold())
    return {token for token in tokens if len(token) > 1 and token not in _TEXT_STOPWORDS}


_DOMAIN_CONCEPT_PATTERNS = {
    "backend_performance": re.compile(
        r"\b(optimi[sz](?:e|ed|ation)?|improv(?:e|ed|ing)|performance|latency|"
        r"response time|p95|slow quer(?:y|ies))\b", re.I
    ),
    "database_work": re.compile(
        r"\b(database|databases|db|postgres(?:ql)?|mysql|sql|quer(?:y|ies)|"
        r"index|indexes|indexing)\b", re.I
    ),
    "api_development": re.compile(
        r"\b(api|apis|rest|restful|endpoint|endpoints|service|services)\b", re.I
    ),
    "caching": re.compile(r"\b(cache|caches|cached|caching|redis)\b", re.I),
    "testing": re.compile(r"\b(test|tests|testing|pytest|unit test|integration test)\b", re.I),
    "deployment": re.compile(
        r"\b(deploy|deployment|deployed|container|containerized|docker|release)\b", re.I
    ),
}


def _evidence_tokens(value: Any) -> set[str]:
    text = _text(value).casefold()
    tokens = _content_tokens(text)
    # Add only narrow, domain-grounded concepts. These support responsibility
    # matching; they do not create exact skill matches or alter skill scoring.
    for concept, pattern in _DOMAIN_CONCEPT_PATTERNS.items():
        if pattern.search(text):
            tokens.add(concept)
    return tokens


def _token_f1(a: Any, b: Any) -> float:
    left, right = _evidence_tokens(a), _evidence_tokens(b)
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    precision = overlap / len(left)
    recall = overlap / len(right)
    if precision + recall == 0:
        return 0.0
    return round(100.0 * (2 * precision * recall / (precision + recall)), 2)


def _evidence_similarity(a: str, b: str) -> float:
    """Blend phrase-aware TF-IDF with transparent content-word overlap."""
    if not a or not b:
        return 0.0
    tfidf_score = _similarity(a, b)
    lexical_score = _token_f1(a, b)
    return round(0.65 * tfidf_score + 0.35 * lexical_score, 2)


def _sentences(value: Any) -> list[str]:
    text = _text(value).strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\\s+|\\n+", text) if part.strip()]
    return parts or [text]


def _responsibility_similarity(description: str, responsibilities: Any) -> float:
    """Score each JD responsibility against the best resume evidence sentence.

    Averaging per-responsibility best matches avoids allowing one repeated phrase
    to dominate the whole score. No missing skill is inferred from this score.
    """
    if isinstance(responsibilities, str):
        targets = [responsibilities] if responsibilities.strip() else []
    elif isinstance(responsibilities, (list, tuple, set)):
        targets = [_text(item).strip() for item in responsibilities if _text(item).strip()]
    else:
        targets = []

    source_sentences = _sentences(description)
    if not targets or not source_sentences:
        return 0.0

    best_scores = []
    for target in targets:
        best = max(
            (_evidence_similarity(sentence, target) for sentence in source_sentences),
            default=0.0,
        )
        best_scores.append(best)
    return round(sum(best_scores) / len(best_scores), 2)


def _skill_overlap(source_skills: Any, target_skills: Any) -> dict[str, Any]:
    source, target = _skill_set(source_skills), _skill_set(target_skills)
    matched, missing = sorted(source & target), sorted(target - source)
    recall = len(matched) / len(target) * 100 if target else 0.0
    jaccard = len(matched) / len(source | target) * 100 if source | target else 0.0
    return {"score": round(.7 * recall + .3 * jaccard, 2) if target else 0.0,
            "matched_skills": matched, "missing_target_skills": missing,
            "additional_source_skills": sorted(source-target)}


def _title_similarity(source: str, target: str) -> float:
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.casefold().replace("_", " ")).strip()
    a, b = norm(source), norm(target)
    if not a or not b: return 0.0
    if a == b: return 100.0
    if "backend" in a and "backend" in b: return max(70.0, _similarity(a, b))
    if "backend" in a and any(t in b for t in ("software engineer", "software developer", "python developer")): return 65.0
    if "backend" in b and any(t in a for t in ("software engineer", "software developer", "python developer")): return 65.0
    return _similarity(a, b)


def role_similarity(source_title: str | None, target_title: str | None,
                    source_skills: Iterable[str] | None = None,
                    target_skills: Iterable[str] | None = None) -> dict[str, Any]:
    source, target = _text(source_title), _text(target_title)
    overlap = _skill_overlap(source_skills or [], target_skills or [])
    title_score = _title_similarity(source, target)
    has_skills = bool(_skill_set(source_skills) or _skill_set(target_skills))
    score = round(.35 * title_score + .65 * overlap["score"], 2) if has_skills else title_score
    return {"score": score, "relationship": "high" if score >= 65 else "moderate" if score >= 30 else "low",
            "title_similarity": title_score, "skill_similarity": overlap["score"],
            "matched_skills": overlap["matched_skills"], "missing_target_skills": overlap["missing_target_skills"],
            "method": "normalized_title_plus_skill_evidence"}


def score_experience_relevance(experiences: list[dict[str, Any]], target_job: dict[str, Any]) -> dict[str, Any]:
    target_title = _text(target_job.get("title") or target_job.get("job_title"))
    target_skills = target_job.get("required_skills") or target_job.get("skills") or []
    if isinstance(target_skills, dict): target_skills = list(target_skills.values())
    target_responsibilities = target_job.get("responsibilities") or []
    if isinstance(target_responsibilities, str): target_responsibilities = [target_responsibilities]
    target_description = _text(target_job.get("description") or target_job.get("job_description"))
    target_context = " ".join([target_title, _text(target_skills), _text(target_responsibilities), target_description])
    results = []
    for item in experiences:
        title = _text(item.get("designation") or item.get("job_title"))
        description = _text(item.get("description"))
        structured_skills = _skill_set(item.get("skills_used", []))
        evidence_skills = structured_skills | _skills_in_text(description) | _skills_in_text(_text(item.get("source_text")))
        skill_match = _skill_overlap(evidence_skills, target_skills)
        title_score = _title_similarity(title, target_title)
        evidence = " ".join([title, _text(item.get("skills_used", [])), description, _text(item.get("source_text"))])
        # Context matching combines TF-IDF phrase similarity with transparent
        # content-word overlap. Responsibility matching compares each JD item
        # with the best supporting sentence in the candidate's experience.
        context_score = _evidence_similarity(evidence, target_context)
        responsibility_score = _responsibility_similarity(description, target_responsibilities)
        score = round(.20 * title_score + .40 * skill_match["score"] + .25 * context_score + .15 * responsibility_score, 2)
        results.append({"experience_id": item.get("experience_id"), "designation": title,
            "employer": item.get("employer"), "relevance_score": score,
            "relevance_level": "high" if score >= 65 else "moderate" if score >= 30 else "low",
            "title_similarity_score": title_score, "skill_match_score": skill_match["score"],
            "context_similarity_score": context_score, "responsibility_similarity_score": responsibility_score,
            "matched_required_skills": skill_match["matched_skills"],
            "missing_required_skills": skill_match["missing_target_skills"],
            "skills_found_in_description": sorted(evidence_skills),
            "role_similarity": {"score": round(.35*title_score+.65*skill_match["score"],2),
                "relationship": "high" if score >= 65 else "moderate" if score >= 30 else "low",
                "title_similarity": title_score, "skill_similarity": skill_match["score"],
                "matched_skills": skill_match["matched_skills"], "missing_target_skills": skill_match["missing_target_skills"],
                "method": "normalized_title_plus_narrative_skill_evidence"}})
    results.sort(key=lambda row: row["relevance_score"], reverse=True)
    # Aggregate by the best relevant role, with a modest contribution from the
    # remaining roles; avoids unrelated short/old roles diluting the score equally.
    if results:
        best = results[0]["relevance_score"]
        remaining = [r["relevance_score"] for r in results[1:]]
        overall = round(.70 * best + .30 * (sum(remaining)/len(remaining) if remaining else best), 2)
    else: overall = 0.0

    career_skills = set().union(*(
        _skill_set(x.get("skills_used", [])) | _skills_in_text(_text(x.get("description"))) for x in experiences
    )) if experiences else set()
    career_match = _skill_overlap(career_skills, target_skills)
    duration_months = sum(max(0, int(x.get("duration_months") or 0)) for x in experiences)
    requirements = target_job.get("experience_requirements") or {}
    min_months = requirements.get("minimum_months") if isinstance(requirements, dict) else None
    max_months = requirements.get("maximum_months") if isinstance(requirements, dict) else None
    range_check = {"candidate_experience_months_from_parsed_roles": duration_months,
        "required_minimum_months": min_months, "required_maximum_months": max_months,
        "status": "not_specified"}
    if max_months is not None:
        range_check["status"] = "within_range" if duration_months <= max_months and (min_months is None or duration_months >= min_months) else "above_range" if duration_months > max_months else "below_range"
    elif min_months is not None:
        range_check["status"] = "meets_minimum" if duration_months >= min_months else "below_minimum"

    return {"target_job_title": target_title, "overall_relevance_score": overall,
        "experience_scores": results,
        "career_evidence": {"relevance_score": career_match["score"],
            "matched_required_skills": career_match["matched_skills"],
            "missing_required_skills": career_match["missing_target_skills"]},
        "experience_range_assessment": range_check,
        "scoring_version": SCORING_VERSION,
        "method": "best-role weighted aggregation; title + narrative skill evidence + evidence-aware context + per-responsibility sentence matching",
        "score_interpretation": {"low": "below 30", "moderate": "30 to below 65", "high": "65 or above"},
        "decision_support_only": True}
