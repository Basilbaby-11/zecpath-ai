
"""Heuristic job description parser for Zecpath AI."""

import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PARSER_VERSION = "0.1.0"


ROLE_ALIASES = {
    "Machine Learning Engineer": [
        "ML Engineer",
        "Machine Learning Engineer",
    ],
    "Natural Language Processing Engineer": [
        "NLP Engineer",
        "Natural Language Processing Engineer",
    ],
    "Artificial Intelligence Engineer": [
        "AI Engineer",
        "Artificial Intelligence Engineer",
    ],
    "Data Scientist": [
        "Data Scientist",
    ],
    "Data Analyst": [
        "Data Analyst",
    ],
    "MLOps Engineer": [
        "MLOps Engineer",
        "Machine Learning Operations Engineer",
    ],
}


# Canonical skill names and common variations.
SKILL_ALIASES = {
    "python": ["python", "python programming"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "sql": ["sql", "structured query language"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "dl"],
    "natural language processing": ["natural language processing", "nlp"],
    "generative ai": ["generative ai", "gen ai"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch", "torch"],
    "fastapi": ["fastapi", "fast api"],
    "django": ["django"],
    "flask": ["flask"],
    "react": ["react", "react.js", "reactjs"],
    "node.js": ["node.js", "nodejs", "node js"],
    "sql": ["sql"],
    "mysql": ["mysql"],
    "postgresql": ["postgresql", "postgres"],
    "mongodb": ["mongodb", "mongo db"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "git": ["git"],
    "communication": ["communication skills", "communication"],
    "problem solving": ["problem-solving", "problem solving"],
    "data analysis": ["data analysis", "data analytics"],
    "tableau": ["tableau"],
}

SKILL_CATEGORIES = {
    "python": "programming_language",
    "javascript": "programming_language",
    "typescript": "programming_language",
    "sql": "programming_language",
    "scikit-learn": "framework",
    "tensorflow": "framework",
    "pytorch": "framework",
    "fastapi": "framework",
    "django": "framework",
    "flask": "framework",
    "react": "framework",
    "node.js": "framework",
    "mysql": "tool",
    "postgresql": "tool",
    "mongodb": "tool",
    "docker": "tool",
    "kubernetes": "tool",
    "aws": "tool",
    "azure": "tool",
    "git": "tool",
    "machine learning": "domain",
    "deep learning": "domain",
    "natural language processing": "domain",
    "generative ai": "domain",
    "data analysis": "domain",
    "communication": "soft_skill",
    "problem solving": "soft_skill",
    "tableau": "tool",
}


def normalize_text(text: str) -> str:
    """Normalize whitespace without changing the original meaning."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_first(pattern: str, text: str, flags: int = re.IGNORECASE):
    """Return the first regex match or None."""
    return re.search(pattern, text, flags)


def normalize_role_name(title: str) -> str:
    """Expand recognized role variations to canonical role names."""
    normalized = title.strip()

    for canonical, aliases in ROLE_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
            normalized = re.sub(
                pattern,
                canonical,
                normalized,
                flags=re.IGNORECASE,
            )

    return normalized


def extract_title(text: str) -> str:
    """Use the first meaningful line as a title candidate."""
    lines = [line.strip(" -*#\t") for line in text.splitlines()]
    lines = [line for line in lines if line]

    if not lines:
        return "Untitled Job"

    # Prefer a line explicitly labelled as the job title.
    for line in lines[:10]:
        match = find_first(
            r"^(?:job title|position|role)\s*:\s*(.+)$", line
        )
        if match:
            return normalize_role_name(match.group(1).strip())

    return normalize_role_name(lines[0][:200]) or "Untitled Job"


def extract_experience(text: str) -> dict[str, Any]:
    """Extract experience ranges and classify the experience level."""
    lower = text.lower()
    minimum_months = None
    maximum_months = None
    experience_level = None

    # Match ranges such as "0 to 1 years of experience".
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*"
        r"(years?|yrs?|months?|mos?)?\s*"
        r"(?:to|-|–)\s*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(years?|yrs?|months?|mos?)"
        r"(?:\s+of)?\s+(?:relevant\s+)?experience",
        lower,
        re.IGNORECASE,
    )

    if range_match:
        first_value = float(range_match.group(1))
        first_unit = range_match.group(2) or range_match.group(4)
        second_value = float(range_match.group(3))
        second_unit = range_match.group(4)

        minimum_months = round(
            first_value * (
                12 if first_unit.startswith(("year", "yr")) else 1
            )
        )
        maximum_months = round(
            second_value * (
                12 if second_unit.startswith(("year", "yr")) else 1
            )
        )
    else:
        single_match = re.search(
            r"(\d+(?:\.\d+)?)\s*"
            r"(years?|yrs?|months?|mos?)"
            r"\s+(?:of\s+)?(?:relevant\s+)?experience",
            lower,
            re.IGNORECASE,
        )

        if single_match:
            value = float(single_match.group(1))
            unit = single_match.group(2)
            minimum_months = round(
                value * (12 if unit.startswith(("year", "yr")) else 1)
            )

    if re.search(r"\b(intern|internship)\b", lower):
        experience_level = "internship"
    elif re.search(r"\b(entry[- ]level|fresher|graduate)\b", lower):
        experience_level = "entry_level"
    elif re.search(r"\b(junior|jr\.?)\b", lower):
        experience_level = "junior"
    elif re.search(r"\b(mid[- ]level|intermediate)\b", lower):
        experience_level = "mid_level"
    elif re.search(r"\b(senior|sr\.?)\b", lower):
        experience_level = "senior"
    elif re.search(r"\b(lead|principal)\b", lower):
        experience_level = "lead"
    elif re.search(r"\b(executive|director|chief)\b", lower):
        experience_level = "executive"
    elif minimum_months is not None:
        experience_level = (
            "entry_level" if minimum_months <= 12 else "other"
        )

    return {
        "minimum_months": minimum_months,
        "maximum_months": maximum_months,
        "experience_level": experience_level,
    }


def extract_skills(text: str) -> list[dict[str, Any]]:
    """Extract all recognized skills and classify their requirement type."""
    results = []
    seen = set()
    sentences = re.split(r"(?<=[.!?\n])\s*", text)

    for sentence in sentences:
        for canonical, aliases in SKILL_ALIASES.items():
            if canonical in seen:
                continue

            found = False
            for alias in aliases:
                if re.search(
                    r"\b" + re.escape(alias) + r"\b",
                    sentence,
                    re.IGNORECASE,
                ):
                    found = True
                    break

            if not found:
                continue

            preferred = bool(
                re.search(
                    r"\b(preferred|preferably|nice to have|"
                    r"good to have|bonus|desirable)\b",
                    sentence,
                    re.IGNORECASE,
                )
            )
            explicitly_required = bool(
                re.search(
                    r"\b(required|must have|mandatory|essential)\b",
                    sentence,
                    re.IGNORECASE,
                )
            )

            results.append({
                "name": canonical,
                "category": SKILL_CATEGORIES.get(canonical, "other"),
                "requirement_type": "preferred" if preferred else "required",
                "minimum_proficiency": None,
                "minimum_years": None,
                "evidence": sentence.strip()[:500] or None,
                "confidence": (
                    0.85 if explicitly_required or preferred else 0.65
                ),
            })
            seen.add(canonical)

    return results



def extract_responsibilities(text: str) -> list[str]:
    """Collect likely responsibility bullets."""
    responsibilities = []
    in_responsibilities = False

    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower().rstrip(":")

        if re.search(
            r"^(key responsibilities|responsibilities|"
            r"what you.ll do|duties)$",
            lower,
        ):
            in_responsibilities = True
            continue

        if re.search(
            r"^(requirements|qualifications|skills|"
            r"education|benefits|about us|how to apply)$",
            lower,
        ):
            in_responsibilities = False
            continue

        if in_responsibilities and stripped:
            bullet = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", stripped)
            if bullet and len(bullet) > 5:
                responsibilities.append(bullet)

    return responsibilities



def extract_education(text: str) -> list[dict[str, Any]]:
    """Extract education requirements and assess mandatory status."""
    requirements = []

    patterns = [
        (
            r"\bPh\.?D\.?\b",
            "PhD",
            r"\b(?:Ph\.?D\.?|doctorate)\b",
        ),
        (
            r"\bmaster'?s?\s+(?:degree|in)\b|\bM\.?Tech\b|\bM\.?Sc\b",
            "Master's degree",
            r"\b(?:master'?s?|M\.?Tech|M\.?Sc)\b",
        ),
        (
            r"\bbachelor'?s?\s+(?:degree|in)\b|\bB\.?Tech\b|\bB\.?E\.?\b|\bB\.?Sc\b",
            "Bachelor's degree",
            r"\b(?:bachelor'?s?|B\.?Tech|B\.?E\.?|B\.?Sc)\b",
        ),
        (
            r"\bdiploma\b",
            "Diploma",
            r"\bdiploma\b",
        ),
    ]

    for pattern, qualification, context_pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        # Examine only the sentence containing this qualification.
        sentence_start = max(
            text.rfind(".", 0, match.start()),
            text.rfind("\n", 0, match.start()),
            text.rfind(";", 0, match.start()),
        ) + 1

        sentence_end_candidates = [
            position
            for position in (
                text.find(".", match.end()),
                text.find("\n", match.end()),
                text.find(";", match.end()),
            )
            if position != -1
        ]
        sentence_end = (
            min(sentence_end_candidates)
            if sentence_end_candidates
            else len(text)
        )

        sentence = text[sentence_start:sentence_end].strip()

        mandatory = bool(
            re.search(
                r"\b(required|must have|mandatory|essential)\b",
                sentence,
                re.IGNORECASE,
            )
        )

        requirements.append({
            "qualification": qualification,
            "field_of_study": [],
            "mandatory": mandatory,
        })

    return requirements


def parse_job_description(
    raw_text: str,
    file_name: str = "job_description.txt",
    document_id: str = "jd-001",
    job_id: str = "job-001",
    language: str = "en",
) -> dict[str, Any]:
    """Convert raw job description text to the Zecpath JD schema shape."""
    text = normalize_text(raw_text)
    lower = text.lower()

    employment_type = None
    for keyword, value in [
        ("full-time", "full_time"),
        ("full time", "full_time"),
        ("part-time", "part_time"),
        ("part time", "part_time"),
        ("contract", "contract"),
        ("internship", "internship"),
        ("freelance", "freelance"),
        ("temporary", "temporary"),
    ]:
        if keyword in lower:
            employment_type = value
            break

    workplace_type = None
    if re.search(r"\b(remote|work from home|work-from-home)\b", lower):
        workplace_type = "remote"
    elif re.search(r"\bhybrid\b", lower):
        workplace_type = "hybrid"
    elif re.search(r"\b(on[- ]site|onsite|in[- ]office)\b", lower):
        workplace_type = "on_site"

    # Conservative location extraction: use explicit labelled location only.
    location_match = find_first(
        r"(?:location|work location|job location)\s*:\s*([^\n]+)", text
    )
    location_text = location_match.group(1).strip() if location_match else None

    location = {"city": None, "region": None, "country": None}
    if location_text:
        parts = [part.strip() for part in location_text.split(",")]
        if len(parts) >= 1:
            location["city"] = parts[0] or None
        if len(parts) >= 2:
            location["region"] = parts[1] or None
        if len(parts) >= 3:
            location["country"] = parts[2] or None

    salary_match = find_first(
        r"(?:salary|compensation|pay)\s*:\s*"
        r"(?:₹|INR|USD|\$|EUR|€|AUD)?\s*([\d,]+)"
        r"(?:\s*(?:-|to)\s*(?:₹|INR|USD|\$|EUR|€|AUD)?\s*([\d,]+))?"
        r"\s*(per\s+year|annually|per\s+month|monthly|per\s+hour)?",
        text,
    )

    compensation = {
        "minimum": None,
        "maximum": None,
        "currency": None,
        "period": None,
    }
    if salary_match:
        compensation["minimum"] = float(salary_match.group(1).replace(",", ""))
        if salary_match.group(2):
            compensation["maximum"] = float(salary_match.group(2).replace(",", ""))
        currency_text = salary_match.group(0).upper()
        if "INR" in currency_text or "₹" in currency_text:
            compensation["currency"] = "INR"
        elif "USD" in currency_text or "$" in currency_text:
            compensation["currency"] = "USD"
        elif "EUR" in currency_text or "€" in currency_text:
            compensation["currency"] = "EUR"
        elif "AUD" in currency_text:
            compensation["currency"] = "AUD"

        period_text = (salary_match.group(3) or "").lower()
        if "hour" in period_text:
            compensation["period"] = "hour"
        elif "month" in period_text:
            compensation["period"] = "month"
        elif "year" in period_text or "annual" in period_text:
            compensation["period"] = "year"

    certification_requirements = []
    for line in text.splitlines():
        if re.search(r"\b(certification|certified|certificate)\b", line, re.I):
            certification_requirements.append(line.strip())

    language_requirements = []
    for language_name in ["English", "Malayalam", "Hindi", "German", "French"]:
        if re.search(r"\b" + re.escape(language_name) + r"\b", text, re.I):
            language_requirements.append({
                "name": language_name,
                "proficiency": None,
                "mandatory": bool(
                    re.search(
                        r"\b(required|must have|fluent|mandatory)\b",
                        text,
                        re.I,
                    )
                ),
            })

    application_match = find_first(
        r"(?:how to apply|application instructions|apply here)\s*:?\s*"
        r"([^\n]+(?:\n(?!\s*$)[^\n]+)?)",
        text,
    )

    summary_match = find_first(
        r"(?:job summary|summary|about the role|role overview)\s*:?\s*"
        r"(.+?)(?=\n\s*\n|\n(?:responsibilities|requirements|qualifications)\b)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    return {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "source_document": {
            "document_id": document_id,
            "file_name": file_name,
            "file_type": Path(file_name).suffix.lstrip(".").lower() or "txt",
            "language": language,
        },
        "title": extract_title(text),
        "department": None,
        "employment_type": employment_type,
        "workplace_type": workplace_type,
        "location": location,
        "summary": normalize_text(summary_match.group(1))
        if summary_match else None,
        "responsibilities": extract_responsibilities(text),
        "skills": extract_skills(text),
        "experience_requirements": extract_experience(text),
        "education_requirements": extract_education(text),
        "certification_requirements": certification_requirements,
        "language_requirements": language_requirements,
        "compensation": compensation,
        "application_instructions": (
            normalize_text(application_match.group(1))
            if application_match else None
        ),
        "metadata": {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "parser_version": PARSER_VERSION,
            "overall_confidence": None,
            "review_status": "pending_review",
        },
    }


def validate_against_schema(
    parsed_data: dict[str, Any],
    schema_path: str = "job_description_schema.json",
) -> None:
    """Raise an error if the output does not match the JSON Schema."""
    try:
        from jsonschema import validate
    except ImportError as exc:
        raise ImportError(
            "Install jsonschema using: python -m pip install jsonschema"
        ) from exc

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    validate(instance=parsed_data, schema=schema)
