"""NLP-based skill entity recognition using spaCy PhraseMatcher.

This is dictionary-guided NLP phrase/entity recognition
It uses spaCy tokenization and case-insensitive phrase matching, then normalizes entities
against the project's canonical skill dictionary.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    import spacy
    from spacy.matcher import PhraseMatcher
except ImportError as exc:  # pragma: no cover - exercised in environments without spaCy
    raise ImportError(
        "spaCy is required for skill NER. Install it with: pip install spacy"
    ) from exc

PARSER_VERSION = "1.0.0"
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
    for start, end, item, matched_term in selected:
        canonical = item["name"]
        span = doc[start:end]
        # Character offsets are taken from the original source text.
        char_start, char_end = span.start_char, span.end_char
        evidence = text[max(0, char_start - 45):min(len(text), char_end + 45)].strip()
        is_canonical = matched_term.casefold() == canonical.casefold()
        confidence = 0.96 if is_canonical else 0.90
        if len(matched_term) <= 2:
            confidence = max(0.50, confidence - 0.10)
        if re.search(r"\b(skills?|technologies|proficient|experienced|worked with|built|developed|implemented|used)\b",
                     evidence, re.I):
            confidence = min(0.99, confidence + 0.03)

        record = {
            "skill_id": _skill_id(canonical),
            "name": canonical,
            "category": item["category"],
            "entity_text": span.text,
            "entity_label": "SKILL",
            "proficiency": None,
            "years_experience": None,
            "evidence": evidence,
            "start_char": char_start,
            "end_char": char_end,
            "confidence": round(confidence, 2),
            "recognition_method": "spacy_phrase_match",
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
                    "proficiency": None,
                    "years_experience": None,
                    "evidence": evidence,
                    "start_char": char_start,
                    "end_char": char_end,
                    "confidence": min(record["confidence"], 0.92),
                    "recognition_method": "stack_expansion",
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
        from parsers.resume_extractor import extract_resume
        resume_text = extract_resume(path)["extracted_text"]
    else:
        raise ValueError("Supported input formats: .txt, .pdf, .docx")

    entities = extract_skill_entities(resume_text, dictionary_path=dictionary_path)
    result = {
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Recognize normalized skill entities using spaCy.")
    parser.add_argument("input", help="Path to a .txt, .pdf, or .docx resume.")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "extracted_resumes"))
    parser.add_argument("--dictionary", default=None, help="Optional custom skill dictionary path.")
    args = parser.parse_args()
    try:
        result = process_resume_file(args.input, args.output_dir, args.dictionary)
    except Exception as exc:
        parser.error(str(exc))
    print(f"SUCCESS: {result['source_document']}")
    print(f"Skill entities recognized: {result['entity_count']}")
    for entity in result["entities"]:
        print(f"  - {entity['name']} | {entity['category']} | confidence={entity['confidence']}")
    print(f"JSON saved: {result['output_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
