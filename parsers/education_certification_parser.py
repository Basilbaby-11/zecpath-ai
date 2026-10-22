"""Heuristic extraction of education and professional certifications from resume text.

Public API:
    parse_education_and_certifications(text) -> dict
    parse_file(input_path, output_path=None) -> dict

Output fields align with the education/certification objects in resume_schema.json.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

PARSER_VERSION = "1.2.0"

# spaCy NLP pipeline with custom entity patterns. This is an NLP-assisted parser:
# spaCy tokenizes the resume and labels domain entities; deterministic normalization
# then converts recognized entities into the project's stable JSON schema.
try:
    import spacy
    from spacy.language import Language
except ImportError:  # Friendly fallback for environments that have not installed requirements.
    spacy = None
    Language = Any

_NLP = None


def _get_nlp():
    """Build and cache a lightweight spaCy NLP pipeline with domain entity labels."""
    global _NLP
    if _NLP is not None:
        return _NLP
    if spacy is None:
        return None
    nlp = spacy.blank("en")
    ruler = nlp.add_pipe("entity_ruler", config={"phrase_matcher_attr": "LOWER", "overwrite_ents": True})
    patterns = []
    for pattern, canonical in DEGREE_PATTERNS:
        # Phrase patterns cover canonical names and common degree abbreviations.
        # The regex-based extractor below remains a normalization/compatibility layer.
        phrase_variants = {
            "Bachelor of Technology": ["B.Tech", "BTech", "Bachelor of Technology"],
            "Bachelor of Engineering": ["B.E.", "BE", "Bachelor of Engineering"],
            "Bachelor of Science": ["B.Sc", "BSc", "Bachelor of Science"],
            "Bachelor of Computer Applications": ["BCA", "Bachelor of Computer Applications"],
            "Bachelor of Commerce": ["B.Com", "BCom", "Bachelor of Commerce"],
            "Master of Technology": ["M.Tech", "MTech", "Master of Technology"],
            "Master of Engineering": ["M.E.", "ME", "Master of Engineering"],
            "Master of Science": ["M.Sc", "MSc", "Master of Science"],
            "Master of Computer Applications": ["MCA", "Master of Computer Applications"],
            "Master of Business Administration": ["MBA", "Master of Business Administration"],
            "Doctor of Philosophy": ["PhD", "Ph.D.", "Doctor of Philosophy"],
            "Associate Degree": ["Associate Degree"],
            "High School Diploma": ["High School Diploma", "High School Certificate"],
            "Higher Secondary Certificate": ["Higher Secondary", "Senior Secondary", "Class XII"],
            "Secondary School Certificate": ["SSLC", "Class X"],
        }.get(canonical, [canonical])
        for phrase in phrase_variants:
            patterns.append({"label": "DEGREE", "pattern": phrase, "id": canonical})
    cert_phrases = [
        "AWS Certified Cloud Practitioner", "AWS Certified Solutions Architect", "AWS Certified Developer",
        "Azure Fundamentals", "AZ-900", "Google Cloud Associate Cloud Engineer", "Google Cloud Digital Leader",
        "Project Management Professional", "PMP", "CompTIA Security+", "Security+", "Certified Ethical Hacker",
        "CEH", "TensorFlow Developer Certificate", "AI-900", "Google Data Analytics Professional Certificate",
        "Cisco Certified Network Associate", "CCNA", "Certified ScrumMaster", "CSM",
    ]
    patterns.extend({"label": "CERTIFICATION", "pattern": phrase} for phrase in cert_phrases)
    patterns.extend([
        {"label": "YEAR", "pattern": [{"TEXT": {"REGEX": "^(19|20)\\d{2}$"}}]},
        {"label": "GRADE", "pattern": [{"LOWER": {"IN": ["cgpa", "gpa"]}}, {"IS_PUNCT": True, "OP": "?"}, {"LIKE_NUM": True}]},
    ])
    ruler.add_patterns(patterns)
    _NLP = nlp
    return _NLP


def extract_nlp_entities(text: str) -> list[dict[str, str]]:
    """Return recognized spaCy entities for auditability/debugging."""
    nlp = _get_nlp()
    if nlp is None:
        return []
    doc = nlp(text)
    return [{"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
            for ent in doc.ents]


EDUCATION_HEADINGS = re.compile(
    r"(?im)^\s*(education|academic background|educational qualifications|qualifications)\s*:?[ \t]*$"
)
CERTIFICATION_HEADINGS = re.compile(
    r"(?im)^\s*(certifications?|licenses?\s*(?:and|&)\s*certifications?|professional certifications?|courses?\s*(?:and|&)\s*certifications?)\s*:?[ \t]*$"
)
ANY_HEADING = re.compile(
    r"(?im)^\s*(?:education|academic background|educational qualifications|qualifications|"
    r"certifications?|licenses?\s*(?:and|&)\s*certifications?|professional certifications?|"
    r"courses?\s*(?:and|&)\s*certifications?|experience|work experience|employment|skills?|"
    r"projects?|summary|profile|objective|achievements?|awards?|languages?|interests?)\s*:?[ \t]*$"
)

DEGREE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:b\.?\s?tech(?:nology)?|bachelor(?:'s)?\s+of\s+technology)\b", re.I), "Bachelor of Technology"),
    (re.compile(r"\b(?:b\.?\s?e\.?|bachelor(?:'s)?\s+of\s+engineering)\b", re.I), "Bachelor of Engineering"),
    (re.compile(r"\b(?:b\.?\s?sc\.?|bachelor(?:'s)?\s+of\s+science)\b", re.I), "Bachelor of Science"),
    (re.compile(r"\b(?:b\.?\s?ca\.?|bachelor(?:'s)?\s+of\s+computer\s+applications)\b", re.I), "Bachelor of Computer Applications"),
    (re.compile(r"\b(?:b\.?\s?com\.?|bachelor(?:'s)?\s+of\s+commerce)\b", re.I), "Bachelor of Commerce"),
    (re.compile(r"\b(?:m\.?\s?tech(?:nology)?|master(?:'s)?\s+of\s+technology)\b", re.I), "Master of Technology"),
    (re.compile(r"\b(?:m\.?\s?e\.?|master(?:'s)?\s+of\s+engineering)\b", re.I), "Master of Engineering"),
    (re.compile(r"\b(?:m\.?\s?sc\.?|master(?:'s)?\s+of\s+science)\b", re.I), "Master of Science"),
    (re.compile(r"\b(?:m\.?\s?ca\.?|master(?:'s)?\s+of\s+computer\s+applications)\b", re.I), "Master of Computer Applications"),
    (re.compile(r"\b(?:m\.?\s?b\.?a\.?|master(?:'s)?\s+of\s+business\s+administration)\b", re.I), "Master of Business Administration"),
    (re.compile(r"\b(?:ph\.?\s?d\.?|doctor(?:ate)?\s+of\s+philosophy)\b", re.I), "Doctor of Philosophy"),
    (re.compile(r"\bassociate(?:'s)?\s+degree\b", re.I), "Associate Degree"),
    (re.compile(r"\bhigh\s+school\s+(?:diploma|certificate)\b", re.I), "High School Diploma"),
    (re.compile(r"\b(?:higher\s+secondary|senior\s+secondary|12th\s+(?:grade|standard)|class\s+xii)\b", re.I), "Higher Secondary Certificate"),
    (re.compile(r"\b(?:sslc|10th\s+(?:grade|standard)|class\s+x)\b", re.I), "Secondary School Certificate"),
]

FIELD_ALIASES = {
    "artificial intelligence and data science": "Artificial Intelligence and Data Science",
    "ai and data science": "Artificial Intelligence and Data Science",
    "computer science and engineering": "Computer Science and Engineering",
    "computer science": "Computer Science",
    "information technology": "Information Technology",
    "data science": "Data Science",
    "artificial intelligence": "Artificial Intelligence",
    "machine learning": "Machine Learning",
    "electronics and communication engineering": "Electronics and Communication Engineering",
    "electrical and electronics engineering": "Electrical and Electronics Engineering",
    "mechanical engineering": "Mechanical Engineering",
    "civil engineering": "Civil Engineering",
    "business administration": "Business Administration",
    "mathematics": "Mathematics",
    "physics": "Physics",
    "commerce": "Commerce",
}

CERTIFICATION_CATALOG: list[tuple[re.Pattern[str], str, str, set[str]]] = [
    (re.compile(r"\baws\s+certified\s+(?:solutions\s+architect\s+)?associate\b", re.I), "AWS Certified Solutions Architect – Associate", "Amazon Web Services", {"cloud", "architecture", "aws"}),
    (re.compile(r"\baws\s+certified\s+developer\s*[–-]?\s*associate\b", re.I), "AWS Certified Developer – Associate", "Amazon Web Services", {"cloud", "development", "aws"}),
    (re.compile(r"\baws\s+certified\s+cloud\s+practitioner\b", re.I), "AWS Certified Cloud Practitioner", "Amazon Web Services", {"cloud", "aws"}),
    (re.compile(r"\bazure\s+fundamentals\s*(?:\(az-900\))?\b", re.I), "Microsoft Certified: Azure Fundamentals", "Microsoft", {"cloud", "azure"}),
    (re.compile(r"\baz-900\b", re.I), "Microsoft Certified: Azure Fundamentals", "Microsoft", {"cloud", "azure"}),
    (re.compile(r"\bgoogle\s+cloud\s+(?:certified\s+)?(?:associate\s+cloud\s+engineer|digital\s+leader)\b", re.I), "Google Cloud Certification", "Google Cloud", {"cloud", "google cloud"}),
    (re.compile(r"\b(?:pmp|project management professional)\b", re.I), "Project Management Professional (PMP)", "Project Management Institute", {"project management", "management"}),
    (re.compile(r"\b(?:comptia\s+security\+|security\+)\b", re.I), "CompTIA Security+", "CompTIA", {"cybersecurity", "security"}),
    (re.compile(r"\b(?:certified\s+ethical\s+hacker|ceh)\b", re.I), "Certified Ethical Hacker (CEH)", "EC-Council", {"cybersecurity", "security"}),
    (re.compile(r"\b(?:tensorflow\s+developer\s+certificate)\b", re.I), "TensorFlow Developer Certificate", "TensorFlow", {"ai", "machine learning", "deep learning"}),
    (re.compile(r"\b(?:microsoft\s+certified:\s*azure\s+ai\s+fundamentals|ai-900)\b", re.I), "Microsoft Certified: Azure AI Fundamentals", "Microsoft", {"ai", "cloud", "azure"}),
    (re.compile(r"\b(?:google\s+data\s+analytics\s+professional\s+certificate)\b", re.I), "Google Data Analytics Professional Certificate", "Google", {"data analytics", "data"}),
    (re.compile(r"\b(?:cisco\s+certified\s+network\s+associate|ccna)\b", re.I), "Cisco Certified Network Associate (CCNA)", "Cisco", {"networking", "it"}),
    (re.compile(r"\b(?:certified\s+scrum\s+master|csm)\b", re.I), "Certified ScrumMaster (CSM)", "Scrum Alliance", {"agile", "project management"}),
]

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "artificial_intelligence": {"ai", "artificial intelligence", "machine learning", "deep learning", "tensorflow", "pytorch", "data science", "data analytics", "nlp"},
    "cloud_computing": {"cloud", "aws", "azure", "google cloud", "gcp", "kubernetes", "devops"},
    "cybersecurity": {"security", "cybersecurity", "ethical hacker", "network security"},
    "data_analytics": {"data", "analytics", "power bi", "tableau", "sql", "business intelligence"},
    "project_management": {"project management", "pmp", "scrum", "agile"},
    "software_development": {"software", "programming", "developer", "java", "python", "web development"},
    "networking": {"network", "ccna", "cisco"},
}


def _clean_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip(" \t•●▪*-\u2022") for line in text.replace("\r", "\n").splitlines() if line.strip()]


def _section_lines(text: str, heading_pattern: re.Pattern[str]) -> list[str]:
    lines = text.replace("\r", "\n").splitlines()
    start = None
    for i, line in enumerate(lines):
        if heading_pattern.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return []
    result = []
    for line in lines[start:]:
        if ANY_HEADING.match(line.strip()):
            break
        if line.strip():
            cleaned = re.sub(r"^\s*(?:[-*•●▪]|\d+[.)])\s*", "", line).strip()
            if cleaned:
                result.append(cleaned)
    return result


def normalize_degree(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" ,;|-")
    for pattern, canonical in DEGREE_PATTERNS:
        if pattern.search(value):
            return canonical
    return value.title() if value else value


def normalize_field(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value).strip(" ,;|-")
    low = normalized.lower()
    for alias, canonical in FIELD_ALIASES.items():
        if alias in low:
            return canonical
    return normalized.title()


def _extract_years(line: str) -> tuple[int | None, int | None]:
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", line)]
    if not years:
        return None, None
    if len(years) == 1:
        return None, years[0]
    return years[0], years[-1]


def _extract_grade(line: str) -> tuple[str | float | None, str | None]:
    match = re.search(r"\b(?:CGPA|GPA)\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*(?:/\s*(\d+(?:\.\d+)?))?", line, re.I)
    if match:
        grade = match.group(1)
        scale = f"out of {match.group(2)}" if match.group(2) else ("10-point scale" if float(grade) <= 10 else None)
        return grade, scale
    match = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*%", line)
    if match:
        return f"{match.group(1)}%", "percentage"
    return None, None


def _infer_unknown_qualification(line: str) -> str | None:
    """Extract a likely unfamiliar qualification phrase without a fixed catalog."""
    cleaned = re.sub(r"\b(?:19|20)\d{2}\b", " ", line)
    cleaned = re.sub(r"\b(?:CGPA|GPA)\s*[:=-]?\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?", " ", cleaned, flags=re.I)
    # Keep the qualification phrase before institution separators when possible.
    parts = re.split(r"\s+(?:at|from)\s+|\s+[|]\s+|\s*,\s*", cleaned, maxsplit=1, flags=re.I)
    phrase = re.sub(r"\s+", " ", parts[0]).strip(" .,:;-|")
    # Keep a qualification and its field separate when an unfamiliar degree uses
    # the common 'Bachelor of X in Y' / 'Diploma in Y' construction.
    split_field = re.match(r"^((?:bachelor|master|doctor(?:ate)?|associate|diploma|doctor of)\b.+?)\s+in\s+([A-Za-z][A-Za-z &/+-]{2,60})$", phrase, re.I)
    if split_field:
        phrase = split_field.group(1).strip()
    if len(phrase) > 100:
        phrase = phrase[:100].rsplit(" ", 1)[0]
    return phrase or None


def _looks_like_certification_candidate(line: str) -> bool:
    """Context fallback for certificates not present in CERTIFICATION_CATALOG."""
    value = re.sub(r"\s+", " ", line).strip(" .;|-•")
    if not (5 <= len(value) <= 220):
        return False
    if re.search(r"https?://|@|\b(?:phone|email|address|objective|responsibilities|developed|managed|worked)\b", value, re.I):
        return False
    # Explicit certificate language is strongest; section context permits other
    # concise credential-like lines such as 'Kubernetes Administrator (CKA)'.
    if re.search(r"\b(certified|certification|certificate|credential|license|licence|diploma|professional certificate)\b", value, re.I):
        return True
    return bool(re.search(r"\b(?:[A-Z]{2,}(?:[-+][A-Z0-9]+)?|administrator|associate|professional|practitioner|specialist|accredited|foundation)\b", value))


def _parse_education_line(line: str, index: int, *, in_education_section: bool = False) -> dict[str, Any] | None:
    """Parse a qualification line, preserving unfamiliar qualification names.

    In a recognized education section, a line can be accepted even when its degree
    is absent from DEGREE_PATTERNS, provided it has education-like context such as
    a year, institution/university wording, or a qualification keyword.
    """
    degree_match = next(((p, canonical) for p, canonical in DEGREE_PATTERNS if p.search(line)), None)
    if not degree_match:
        has_qualification_word = bool(re.search(
            r"\b(degree|diploma|bachelor|master|doctorate|ph\.?d|associate|qualification|certificate|higher secondary|senior secondary|sslc|b\.?pharm|pharmacy|engineering|technology)\b",
            line, re.I
        ))
        has_education_context = bool(re.search(
            r"\b(?:19|20)\d{2}\b|\b(?:university|college|institute|school|polytechnic)\b|\b(?:pursuing|graduated|expected)\b",
            line, re.I
        ))
        if not has_qualification_word and not (in_education_section and has_education_context):
            return None
        # Preserve unknown qualifications rather than forcing a known alias.
        degree = _infer_unknown_qualification(line) or normalize_degree(line)
    else:
        degree = degree_match[1]
    years_start, years_end = _extract_years(line)
    grade, grade_scale = _extract_grade(line)
    field = None
    low = line.lower()
    for alias in sorted(FIELD_ALIASES, key=len, reverse=True):
        if alias in low:
            field = FIELD_ALIASES[alias]
            break
    if field is None:
        # Capture a field after common connectors, avoiding date/grade fragments.
        m = re.search(r"\b(?:in|of)\s+([A-Za-z][A-Za-z &/+-]{2,60}?)(?=\s+(?:at|from|\|)|[,;|]|\s+\(?\d{4}\b|$)", line, re.I)
        if m:
            candidate = m.group(1).strip()
            if candidate.lower() not in {"science", "technology", "engineering", "arts"}:
                field = normalize_field(candidate)
    # Remove known degree, dates and grade fragments to find a likely institution.
    institution_part = line
    for pattern, _ in DEGREE_PATTERNS:
        institution_part = pattern.sub(" ", institution_part)
    if not degree_match and degree:
        institution_part = re.sub(re.escape(degree), " ", institution_part, flags=re.I)
    # Remove the detected field phrase and common connectors before retaining institution text.
    if field:
        institution_part = re.sub(re.escape(field), " ", institution_part, flags=re.I)
        for alias, canonical in FIELD_ALIASES.items():
            if canonical == field:
                institution_part = re.sub(re.escape(alias), " ", institution_part, flags=re.I)
    institution_part = re.sub(r"\b(?:19|20)\d{2}\b|\b(?:CGPA|GPA)\s*[:=-]?\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?|\b\d+(?:\.\d+)?\s*%", " ", institution_part, flags=re.I)
    institution_part = re.sub(r"\b(?:in|of|from|at)\b", " ", institution_part, flags=re.I)
    institution_part = re.sub(r"\s+", " ", institution_part).strip(" ,;|:-")
    institution = institution_part if len(institution_part) >= 3 and institution_part.lower() not in {"bachelor", "master", "science", "technology", "engineering", "commerce", "degree"} else None
    # Don't claim a likely field or qualification itself is the institution.
    if institution and (institution.lower() == (field or "").lower() or institution.lower() == degree.lower()):
        institution = None
    return {
        "education_id": f"EDU-{index:03d}", "institution": institution or None,
        "qualification": degree, "field_of_study": field,
        "start_year": years_start, "end_year": years_end,
        "grade": grade, "grade_scale": grade_scale, "confidence": 0.72 if institution else 0.58,
    }


def _certification_category(name: str, tags: set[str] | None = None) -> list[str]:
    haystack = (name + " " + " ".join(tags or set())).lower()
    categories = [category for category, keywords in CATEGORY_KEYWORDS.items() if any(k in haystack for k in keywords)]
    return categories or ["other"]


def _parse_certification_line(line: str) -> dict[str, Any] | None:
    original = re.sub(r"\s+", " ", line).strip(" .;|-")
    if len(original) < 4 or len(original) > 220:
        return None
    if re.search(r"\b(certification|certified|certificate|license|licence|credential|diploma)\b", original, re.I) is None:
        # Recognized short-form certification names.
        if not re.search(r"\b(?:PMP|CCNA|CEH|CSM|AZ-900|AI-900|Security\+)\b", original, re.I):
            return None
    canonical = original
    issuer = None
    tags: set[str] = set()
    for pattern, name, provider, category_tags in CERTIFICATION_CATALOG:
        if pattern.search(original):
            canonical, issuer, tags = name, provider, category_tags
            break
    if issuer is None:
        issuer_match = re.search(r"\b(?:by|from|issued by)\s+([A-Z][A-Za-z0-9& .'-]{2,60})", original)
        if issuer_match:
            issuer = issuer_match.group(1).strip(" .,-")
            canonical = re.sub(r"\s+(?:by|from|issued by)\s+" + re.escape(issuer) + r"\s*$", "", canonical, flags=re.I).strip()
    issue_date = expiry_date = credential_id = credential_url = None
    m = re.search(r"\b(?:issued|earned|completed)\s*[:\-]?\s*((?:19|20)\d{2}(?:-\d{2})?)\b", original, re.I)
    if m:
        issue_date = m.group(1)
    m = re.search(r"\b(?:expires?|valid\s+until)\s*[:\-]?\s*((?:19|20)\d{2}(?:-\d{2})?)\b", original, re.I)
    if m:
        expiry_date = m.group(1)
    m = re.search(r"\b(?:credential\s*(?:id|#)|certificate\s*(?:id|#)|id)\s*[:#=-]?\s*([A-Za-z0-9-]{4,})", original, re.I)
    if m:
        credential_id = m.group(1)
    m = re.search(r"https?://\S+", original, re.I)
    if m:
        credential_url = m.group(0).rstrip(".,)")
    return {"name": canonical, "issuer": issuer, "issue_date": issue_date,
            "credential_id": credential_id,
            "credential_url": credential_url, "confidence": 0.85 if issuer else 0.68,
            "relevance_categories": _certification_category(canonical, tags)}


def parse_education_and_certifications(text: str) -> dict[str, Any]:
    """Extract education records and certifications from resume text.

    This is a rule-based baseline. Review low-confidence results before using them
    for hiring decisions; it does not infer credentials that are not stated.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    education_lines = _section_lines(text, EDUCATION_HEADINGS)
    certification_lines = _section_lines(text, CERTIFICATION_HEADINGS)
    has_education_section = bool(education_lines) or bool(EDUCATION_HEADINGS.search(text))
    has_certification_section = bool(certification_lines) or bool(CERTIFICATION_HEADINGS.search(text))
    # spaCy identifies domain entities across the whole resume, including documents
    # whose section headings are missing or unconventional. Keep the source line as
    # context so the existing structured-field normalizers can recover dates/grades.
    nlp_entities = extract_nlp_entities(text)
    lines = _clean_lines(text)
    entity_lines = {entity["text"].casefold() for entity in nlp_entities}
    nlp_candidate_lines = [line for line in lines if any(entity in line.casefold() for entity in entity_lines)]
    if not education_lines:
        # No recognized heading: use NLP entity hits plus broad qualification/context cues.
        education_lines = [line for line in lines if any(p.search(line) for p, _ in DEGREE_PATTERNS)]
        education_lines.extend(line for line in lines if re.search(
            r"\b(?:bachelor|master|doctorate|associate degree|diploma|degree|qualification|pharmacy|university|college)\b.*\b(?:19|20)\d{2}\b|\b(?:19|20)\d{2}\b.*\b(?:university|college|degree|diploma)\b",
            line, re.I))
        education_lines.extend(line for line in nlp_candidate_lines if any(e["label"] == "DEGREE" and e["text"].casefold() in line.casefold() for e in nlp_entities))
    if not certification_lines:
        certification_lines = [line for line in lines if re.search(r"\b(certification|certified|certificate|license|licence|PMP|CCNA|CEH|CSM|AZ-900|AI-900)\b", line, re.I)]
        certification_lines.extend(line for line in nlp_candidate_lines if any(e["label"] == "CERTIFICATION" and e["text"].casefold() in line.casefold() for e in nlp_entities))
    education: list[dict[str, Any]] = []
    seen_edu: set[str] = set()
    for line in education_lines:
        record = _parse_education_line(line, len(education) + 1, in_education_section=has_education_section)
        if record:
            key = "|".join(str(record.get(k) or "").lower() for k in ("qualification", "field_of_study", "institution", "end_year"))
            if key not in seen_edu:
                seen_edu.add(key)
                record["education_id"] = f"EDU-{len(education)+1:03d}"
                education.append(record)
    certifications: list[dict[str, Any]] = []
    seen_certs: set[str] = set()
    # If a certification section exists, consider any concise credential-like line,
    # even when it is absent from the known certification catalog.
    if has_certification_section:
        certification_lines = [line for line in certification_lines if _looks_like_certification_candidate(line)]
    for line in certification_lines:
        record = _parse_certification_line(line)
        if record is None and has_certification_section and _looks_like_certification_candidate(line):
            original = re.sub(r"\s+", " ", line).strip(" .;|-")
            record = {
                "name": original, "issuer": None, "normalized_name": None,
                "credential_id": None,
                "credential_url": None, "confidence": 0.52,
                "relevance_categories": _certification_category(original),
            }
        if record:
            key = record["name"].casefold()
            if key not in seen_certs:
                seen_certs.add(key)
                certifications.append(record)
    return {
        "education": education,
        "certifications": certifications,
    }


def parse_file(input_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    input_file = Path(input_path)
    result = parse_education_and_certifications(input_file.read_text(encoding="utf-8", errors="replace"))
    result["source_file"] = input_file.name
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract education and certifications from a TXT resume.")
    parser.add_argument("input", help="Path to a plain-text resume")
    parser.add_argument("--output", help="Output JSON path (default: print to stdout)")
    args = parser.parse_args()
    result = parse_file(args.input, args.output)
    if not args.output:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
