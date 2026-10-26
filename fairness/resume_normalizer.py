"""Normalize heterogeneous combined-resume records into a stable scoring shape."""
from __future__ import annotations
from typing import Any, Mapping


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def normalize_resume(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a predictable, scoring-oriented record without inventing missing facts.

    Accepts records from scripts/combined_resume_pipeline.py and common nested
    resume structures. Original identity fields are retained only in `personal_info`
    so callers can pass the result through `mask_personal_attributes` before scoring.
    """
    if not isinstance(record, Mapping):
        raise TypeError("Resume record must be a mapping/object.")
    candidate = record.get("candidate") if isinstance(record.get("candidate"), Mapping) else {}
    personal = record.get("personal_info") if isinstance(record.get("personal_info"), Mapping) else {}
    location = candidate.get("location") if isinstance(candidate.get("location"), Mapping) else {}
    skills_raw = record.get("skills", candidate.get("skills", []))
    skills: list[str] = []
    seen: set[str] = set()
    for item in _as_list(skills_raw):
        name = item.get("name") or item.get("skill") if isinstance(item, Mapping) else item
        name = _clean_text(name)
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            skills.append(name)
    experiences = _as_list(record.get("experience", record.get("experiences", [])))
    education = _as_list(record.get("education", []))
    certifications = _as_list(record.get("certifications", []))
    languages = _as_list(record.get("languages", []))
    candidate_id = _clean_text(record.get("candidate_id") or candidate.get("candidate_id"))
    source_doc = record.get("source_document")
    if isinstance(source_doc, Mapping):
        source_doc = source_doc.get("file_name") or source_doc.get("document_id")
    return {
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "source_document": _clean_text(source_doc),
        "status": _clean_text(record.get("status")) or "success",
        "professional_summary": _clean_text(candidate.get("professional_summary") or record.get("professional_summary") or record.get("summary")),
        "skills": skills,
        "skill_entities": _as_list(record.get("skill_entities", [])),
        "experience": experiences,
        "education": education,
        "certifications": certifications,
        "languages": languages,
        "personal_info": {
            "name": _clean_text(personal.get("name") or candidate.get("full_name") or record.get("name")),
            "email": _clean_text(personal.get("email") or candidate.get("email") or record.get("email")),
            "phone": _clean_text(personal.get("phone") or candidate.get("phone") or record.get("phone")),
            "location": {
                "city": _clean_text(location.get("city")),
                "region": _clean_text(location.get("region")),
                "country": _clean_text(location.get("country")),
            },
        },
        "metadata": {
            "source_status": _clean_text(record.get("status")) or "unknown",
            "normalization_warnings": (["candidate_id_missing"] if not candidate_id else []) + (["resume_processing_failed"] if record.get("status") == "failed" else []),
        },
    }


def normalize_resume_batch(payload: Any) -> dict[str, Any]:
    """Normalize a list or the repository's {resumes: [...]} batch payload."""
    if isinstance(payload, Mapping):
        records = payload.get("resumes")
        if records is None:
            records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        raise TypeError("Batch payload must be a list or an object containing 'resumes'.")
    normalized = [normalize_resume(row) for row in records]
    return {"pipeline": "fairness_resume_normalization", "total": len(normalized), "resumes": normalized}
