"""NLP-based skill entity recognition using spaCy PhraseMatcher.

This is dictionary-guided NLP phrase/entity recognition
It uses spaCy tokenization and case-insensitive phrase matching, then normalizes entities
against the project's canonical skill dictionary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from parsers.resume_extractor import extract_one

try:
    import spacy
    from spacy.matcher import PhraseMatcher
except ImportError as exc:  # pragma: no cover - exercised in environments without spaCy
    raise ImportError(
        "spaCy is required for skill NER. Install it with: pip install spacy"
    ) from exc

PARSER_VERSION = "1.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DICTIONARY_PATH = PROJECT_ROOT / "data" / "skill_dictionary.json"
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def load_skill_dictionary(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and validate canonical skills, aliases, categories and stack expansions."""
    dictionary_path = Path(path) if path else DEFAULT_DICTIONARY_PATH
    with dictionary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    skills = payload.get("skills")
    if not isinstance(skills, list):
        raise ValueError("Skill dictionary must contain a 'skills' list.")

    allowed_categories = {
        "programming_language", "framework", "tool", "domain", "soft_skill", "other"
    }
    names: set[str] = set()
    for item in skills:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("Each dictionary entry must be an object with a non-empty name.")
        if item.get("category") not in allowed_categories:
            raise ValueError(f"Unsupported category for skill: {item.get('name')}")
        key = item["name"].casefold()
        if key in names:
            raise ValueError(f"Duplicate canonical skill name: {item['name']}")
        names.add(key)
        if not isinstance(item.get("aliases", []), list):
            raise ValueError(f"Aliases must be a list for skill: {item['name']}")
        if not isinstance(item.get("expands_to", []), list):
            raise ValueError(f"expands_to must be a list for skill: {item['name']}")
    return skills


def _skill_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")


def _candidate_id(
    *, email: str | None, phone: str | None, name: str | None, source_name: str
) -> str:
    """Return a stable candidate ID so PDF/DOCX copies of one resume share an ID.

    Email is preferred, then phone. If neither exists, use normalized name plus
    the filename stem so unrelated candidates with the same name are less likely
    to collide. The ID is a stable pseudonymous identifier, not anonymization.
    """
    if email and email.strip():
        identity = "email:" + email.strip().casefold()
    elif phone and phone.strip():
        digits = re.sub(r"\D", "", phone)
        identity = "phone:" + digits if digits else "phone:" + phone.strip().casefold()
    elif name and name.strip():
        identity = "name:" + re.sub(r"\s+", " ", name).strip().casefold()
        identity += "|file:" + Path(source_name).stem.casefold()
    else:
        identity = "file:" + Path(source_name).stem.casefold()

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
    return f"CAND-{digest}"


def _build_matcher(nlp: Any, dictionary: list[dict[str, Any]]) -> tuple[Any, dict[str, tuple[dict[str, Any], str]]]:
    """Build a case-insensitive PhraseMatcher and map each phrase to canonical metadata."""
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    phrase_metadata: dict[str, tuple[dict[str, Any], str]] = {}
    patterns_by_skill: dict[str, list[Any]] = {}

    for item in dictionary:
        canonical = item["name"]
        terms = [canonical, *item.get("aliases", [])]
        seen_terms: set[str] = set()
        for term in terms:
            if not isinstance(term, str) or not term.strip():
                continue
            normalized_term = term.strip()
            term_key = normalized_term.casefold()
            if term_key in seen_terms:
                continue
            seen_terms.add(term_key)
            doc = nlp.make_doc(normalized_term)
            if not len(doc):
                continue
            # A stable phrase ID is used by PhraseMatcher; metadata maps it back to the skill.
            phrase_id = f"SKILL::{canonical.casefold()}::{term_key}"
            patterns_by_skill.setdefault(canonical.casefold(), []).append(doc)
            phrase_metadata[phrase_id] = (item, normalized_term)
            matcher.add(phrase_id, [doc])
    return matcher, phrase_metadata



_SECTION_PATTERNS = {
    "skills": re.compile(r"^(technical\s+skills|skills|core\s+competencies|key\s+skills|technologies|technical\s+expertise)\s*:?$", re.I),
    "experience": re.compile(r"^(work\s+experience|professional\s+experience|experience|employment\s+history|internship\s+experience)\s*:?$", re.I),
    "projects": re.compile(r"^(projects|personal\s+projects|academic\s+projects|key\s+projects|project\s+experience)\s*:?$", re.I),
    "education": re.compile(r"^(education|academic\s+background|qualifications)\s*:?$", re.I),
    "certifications": re.compile(r"^(certifications?|licenses?\s+and\s+certifications|courses|training)\s*:?$", re.I),
    "summary": re.compile(r"^(professional\s+summary|summary|profile|career\s+objective|objective|about\s+me)\s*:?$", re.I),
}


def _section_at(text: str, offset: int) -> str:
    """Infer the nearest recognized resume section heading before a character offset."""
    section = "other"
    for line in text[:offset].splitlines():
        heading = re.sub(r"^[\s#•*\-]+|[\s:]+$", "", line).strip()
        if len(heading) <= 60:
            for section_name, pattern in _SECTION_PATTERNS.items():
                if pattern.match(heading):
                    section = section_name
                    break
    return section


def _score_skill_confidence(
    *, match_quality: float, context_quality: float,
    evidence_strength: float, repetition: float,
) -> float:
    """Calculate a transparent 0-100 heuristic score (not a probability)."""
    components = (match_quality, context_quality, evidence_strength, repetition)
    if any(not isinstance(value, (int, float)) or not 0 <= value <= 100 for value in components):
        raise ValueError("Confidence components must be numeric values from 0 to 100.")
    return round(
        0.40 * match_quality + 0.30 * context_quality
        + 0.20 * evidence_strength + 0.10 * repetition,
        2,
    )


def _context_quality(section: str) -> float:
    return {
        "skills": 100.0,
        "projects": 90.0,
        "experience": 90.0,
        "education": 80.0,
        "certifications": 80.0,
        "summary": 70.0,
        "other": 55.0,
    }.get(section, 55.0)


def _local_evidence(text: str, start: int, end: int) -> str:
    """Get local line evidence without accidentally crossing into another section."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()


def _evidence_strength(evidence: str, section: str) -> float:
    """Estimate how much local text supports a meaningful skill mention."""
    action_pattern = r"\b(built|developed|implemented|designed|deployed|created|maintained|used|utilized|integrated|trained|analyzed|automated|engineered|managed|worked\s+with|experience\s+with|proficient\s+in)\b"
    if re.search(action_pattern, evidence, re.I):
        return 100.0
    if section == "skills" or re.search(r"\b(skills?|technologies|technical\s+stack|toolkit)\b", evidence, re.I):
        return 65.0
    if len(evidence.split()) >= 12:
        return 75.0
    return 55.0


def _repetition_score(occurrence_sections: list[str]) -> float:
    """Reward corroboration, not repeated mentions in unrelated boilerplate."""
    relevant = [section for section in occurrence_sections if section != "other"]
    if len(set(relevant)) >= 2:
        return 100.0
    if len(relevant) >= 2:
        return 80.0
    return 60.0

def extract_skill_entities(
    text: str,
    dictionary_path: str | Path | None = None,
    include_stack_components: bool = True,
) -> list[dict[str, Any]]:
    """Recognize skills in text and return normalized, deduplicated entity records."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        return []

    dictionary = load_skill_dictionary(dictionary_path)
    # Blank English pipeline gives robust tokenization without downloading a model.
    nlp = spacy.blank("en")
    matcher, phrase_metadata = _build_matcher(nlp, dictionary)
    doc = nlp(text)
    candidates: list[tuple[int, int, dict[str, Any], str]] = []

    for match_id, start, end in matcher(doc):
        phrase_id = nlp.vocab.strings[match_id]
        metadata = phrase_metadata.get(phrase_id)
        if metadata is None:
            continue
        item, matched_term = metadata
        span = doc[start:end]
        candidates.append((start, end, item, matched_term))

    # Resolve overlapping phrases by choosing the longest phrase at each overlapping region.
    candidates.sort(key=lambda row: (-(row[1] - row[0]), row[0], row[2]["name"].casefold()))
    selected: list[tuple[int, int, dict[str, Any], str]] = []
    for candidate in candidates:
        start, end, *_ = candidate
        if any(start < prior_end and end > prior_start for prior_start, prior_end, *_ in selected):
            continue
        selected.append(candidate)
    selected.sort(key=lambda row: (row[0], row[1]))

    found: dict[str, dict[str, Any]] = {}
    canonical_lookup = {item["name"].casefold(): item for item in dictionary}
    occurrences_by_skill: dict[str, list[str]] = {}
    for occurrence_start, _occurrence_end, occurrence_item, _occurrence_term in selected:
        occurrence_key = occurrence_item["name"].casefold()
        occurrences_by_skill.setdefault(occurrence_key, []).append(_section_at(text, doc[occurrence_start].idx))

    for start, end, item, matched_term in selected:
        canonical = item["name"]
        span = doc[start:end]
        # Character offsets are taken from the original source text.
        char_start, char_end = span.start_char, span.end_char
        evidence = text[max(0, char_start - 45):min(len(text), char_end + 45)].strip()
        is_canonical = matched_term.casefold() == canonical.casefold()
        match_quality = 100.0 if is_canonical else 90.0
        # Very short aliases (for example, "R") are more prone to false positives.
        if len(matched_term.strip()) <= 2:
            match_quality = 75.0
        section = _section_at(text, char_start)
        context_quality = _context_quality(section)
        local_evidence = _local_evidence(text, char_start, char_end)
        evidence_strength = _evidence_strength(local_evidence, section)
        repetition = _repetition_score(occurrences_by_skill.get(canonical.casefold(), [section]))
        confidence_score = _score_skill_confidence(
            match_quality=match_quality,
            context_quality=context_quality,
            evidence_strength=evidence_strength,
            repetition=repetition,
        )

        record = {
            "skill_id": _skill_id(canonical),
            "name": canonical,
            "category": item["category"],
            "entity_text": span.text,
            "entity_label": "SKILL",
            "confidence_score": confidence_score,
            # Keep the existing 0-1 confidence field for API compatibility.
            "confidence": round(confidence_score / 100.0, 4),
            "score_breakdown": {
                "match_quality": match_quality,
                "context_quality": context_quality,
                "evidence_strength": evidence_strength,
                "repetition": repetition,
            },
        }
        key = canonical.casefold()
        previous = found.get(key)
        if previous is None or record["confidence"] > previous["confidence"]:
            found[key] = record

        if include_stack_components:
            for component in item.get("expands_to", []):
                component_item = canonical_lookup.get(component.casefold())
                if component_item is None:
                    continue
                component_key = component.casefold()
                stack_record = {
                    "skill_id": _skill_id(component),
                    "name": component,
                    "category": component_item["category"],
                    "entity_text": span.text,
                    "entity_label": "SKILL",
                    "confidence_score": min(record["confidence_score"], 92.0),
                    "confidence": round(min(record["confidence_score"], 92.0) / 100.0, 4),
                    "score_cap_applied": 92.0,
                    "score_breakdown": record["score_breakdown"],
                }
                previous_component = found.get(component_key)
                if previous_component is None or stack_record["confidence"] > previous_component["confidence"]:
                    found[component_key] = stack_record

    return sorted(found.values(), key=lambda row: row["name"].casefold())


def process_resume_file(
    file_path: str | Path,
    output_dir: str | Path | None = None,
    dictionary_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Resume not found: {path}")
    if path.suffix.lower() == ".txt":
        resume_text = path.read_text(encoding="utf-8")
    elif path.suffix.lower() in {".pdf", ".docx"}:
        from parsers.resume_extractor import extract_one
        resume_text = extract_one(path)["cleaned_text"]
    else:
        raise ValueError("Supported input formats: .txt, .pdf, .docx")

    entities = extract_skill_entities(resume_text, dictionary_path=dictionary_path)
    identity = extract_basic_information(resume_text, path.name, dictionary_path)
    result = {
        "candidate_id": _candidate_id(
            email=identity["email"], phone=identity["phone"],
            name=identity["name"], source_name=path.name,
        ),
        "source_document": path.name,
        "extraction_status": "success",
        "entity_count": len(entities),
        "entities": entities,
        "recognizer": "spaCy PhraseMatcher (dictionary-guided)",
        "parser_version": PARSER_VERSION,
    }
    destination = Path(output_dir) if output_dir else PROJECT_ROOT / "data" / "extracted_resumes"
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / f"{path.stem}_skill_entities.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    result["output_file"] = str(output_path)
    return result


def extract_basic_information(text: str, source_name: str, dictionary_path: str | Path | None = None) -> dict[str, Any]:
    """Return a simple, readable summary for one resume."""
    cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Use the first plausible short line as the candidate name, unless it looks like a heading.
    name = None
    heading_words = {"resume", "curriculum vitae", "cv", "profile", "about me", "contact"}
    for line in cleaned_lines[:8]:
        candidate = re.sub(r"\s+", " ", line).strip(" |•-\t")
        if (len(candidate) <= 60 and len(candidate.split()) <= 5
                and not re.search(r"[@\d:/]", candidate)
                and candidate.casefold() not in heading_words
                and re.search(r"[A-Za-z]", candidate)):
            name = candidate
            break

    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    phone_match = re.search(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", text)
    skills = extract_skill_entities(text, dictionary_path=dictionary_path)
    email = email_match.group(0) if email_match else None
    phone = re.sub(r"\s+", " ", phone_match.group(0)).strip() if phone_match else None
    return {
        "candidate_id": _candidate_id(
            email=email, phone=phone, name=name, source_name=source_name,
        ),
        "resume": source_name,
        "name": name,
        "email": email,
        "phone": phone,
        "skills": sorted({item["name"] for item in skills}, key=str.casefold),
    }


def _read_resume_text(path: Path) -> str:
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".pdf", ".docx"}:
        from parsers.resume_extractor import extract_one
        return extract_one(path)["cleaned_text"]
    raise ValueError("Supported input formats: .txt, .pdf, .docx")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract basic information and skills from one or more resumes into one JSON file."
    )
    parser.add_argument("input", help="Path to a resume file or a folder containing resumes.")
    parser.add_argument(
        "--output", default=str(PROJECT_ROOT / "data" / "extracted_resumes" / "batch_skill_confidence.json"),
        help="Single JSON output file (default: data/extracted_resumes/batch_skill_confidence.json)."
    )
    parser.add_argument("--recursive", action="store_true", help="Also search subfolders when input is a folder.")
    parser.add_argument("--dictionary", default=None, help="Optional custom skill dictionary path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input path does not exist: {input_path}")

    if input_path.is_file():
        files = [input_path] if input_path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    elif input_path.is_dir():
        iterator = input_path.rglob("*") if args.recursive else input_path.iterdir()
        files = sorted(path for path in iterator if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS)
    else:
        files = []

    if not files:
        parser.error(f"No supported resume files (.txt, .pdf, .docx) found in: {input_path}")

    results = []
    failures = []
    for path in files:
        try:
            resume_text = _read_resume_text(path)
            summary = extract_basic_information(resume_text, path.name, args.dictionary)
            skill_entities = extract_skill_entities(resume_text, dictionary_path=args.dictionary)
            # Keep the existing simple skill-name list for compatibility, and add
            # detailed per-skill records with confidence scores and score breakdowns.
            summary["skills"] = sorted({entity["name"] for entity in skill_entities}, key=str.casefold)
            summary["skill_entities"] = skill_entities
            summary["status"] = "success"
            results.append(summary)
        except Exception as exc:
            failures.append({"resume": path.name, "status": "failed", "error": str(exc)})

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_resumes": len(files),
        "successful": len(results),
        "failed": len(failures),
        "resumes": results,
        "errors": failures,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Processed {len(files)} resume(s): {len(results)} successful, {len(failures)} failed.")
    print(f"Single output file saved: {output_path}")
    for item in results:
        print(f"- {item['resume']}: {item['name'] or 'Name not found'} | {len(item['skills'])} skills with confidence details")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
