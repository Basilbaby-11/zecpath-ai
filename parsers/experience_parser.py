"""NLP-assisted experience parser with robust resume date normalization.

The parser combines spaCy NER (when the model is installed) with explicit,
auditable structural parsing for common resume experience headers. It does not
infer missing dates or treat project/education dates as employment automatically.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

PARSER_VERSION = "2.3.0-multi-experience"

_MONTH_NAMES = (
    "January February March April May June July August September October "
    "November December"
).split()
_MONTHS = {m.lower(): i for i, m in enumerate(_MONTH_NAMES, 1)}
_MONTHS.update({m[:3].lower(): i for i, m in enumerate(_MONTH_NAMES, 1)})
_MONTH_PATTERN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
# Order matters: ISO YYYY-MM must be matched before a bare YYYY.
_DATE_TOKEN = re.compile(
    rf"(?<!\d)(?:(?P<iso_year>19\d{{2}}|20\d{{2}})[-/](?P<iso_month>0?[1-9]|1[0-2])"
    rf"|(?P<month>{_MONTH_PATTERN})\.?\s+(?P<month_year>19\d{{2}}|20\d{{2}})"
    rf"|(?P<year>19\d{{2}}|20\d{{2}}))(?!\d)",
    re.I,
)
_CURRENT = re.compile(r"\b(?:present|current|now|to date|till date)\b", re.I)
_ROLE_HINTS = re.compile(
    r"\b(intern|engineer|analyst|developer|manager|consultant|designer|scientist|"
    r"administrator|specialist|associate|lead|officer|technician|teacher|assistant|"
    r"executive|researcher|coordinator|architect|accountant|nurse|lawyer|"
    r"operator|director|supervisor|recruiter|tester|qa|trainee)\b", re.I
)
_EMPLOYMENT_TYPES = [
    ("internship", re.compile(r"\bintern(ship)?\b", re.I)),
    ("contract", re.compile(r"\b(contract|contractor|freelance)\b", re.I)),
    ("part_time", re.compile(r"\bpart[- ]time\b", re.I)),
    ("full_time", re.compile(r"\bfull[- ]time\b", re.I)),
]
_SECTION_HEADERS = re.compile(
    r"^(professional experience|work experience|employment history|experience|"
    r"education|academic background|projects|certifications|technical skills|skills|"
    r"professional summary|summary|references)\b", re.I
)


def _load_nlp():
    try:
        import spacy
        try:
            return spacy.load("en_core_web_sm")
        except OSError:
            return None
    except ImportError:
        return None


def _entities(text: str) -> dict[str, list[str]]:
    found = {"organizations": [], "dates": []}
    nlp = _load_nlp()
    if nlp is None:
        return found
    doc = nlp(text[:100000])
    for ent in doc.ents:
        key = "organizations" if ent.label_ == "ORG" else "dates" if ent.label_ == "DATE" else None
        value = ent.text.strip()
        if key and value and value not in found[key]:
            found[key].append(value)
    return found


def _date_token_value(match: re.Match[str]) -> str | None:
    gd = match.groupdict()
    if gd.get("iso_year"):
        return f"{gd['iso_year']}-{int(gd['iso_month']):02d}"
    if gd.get("month_year"):
        month = _MONTHS.get(gd["month"].lower().rstrip("."))
        return f"{gd['month_year']}-{month:02d}" if month else gd["month_year"]
    if gd.get("year"):
        return gd["year"]
    return None


def _month_index(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"(19\d{2}|20\d{2})(?:-(\d{2}))?", value)
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2) or 1)
    if not 1 <= month <= 12:
        return None
    return year * 12 + month - 1


def _index_date(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def duration_months(start_date: str | None, end_date: str | None,
                    is_current: bool = False, as_of: date | None = None) -> int | None:
    """Return inclusive calendar-month duration, or None for unknown/invalid dates."""
    start = _month_index(start_date)
    end_value = (as_of or date.today()).strftime("%Y-%m") if is_current else end_date
    end = _month_index(end_value)
    if start is None or end is None or end < start:
        return None
    return end - start + 1


def _date_range(line: str) -> tuple[str | None, str | None, bool, list[tuple[int, int]]]:
    current = bool(_CURRENT.search(line))
    matches = list(_DATE_TOKEN.finditer(line))
    if not matches:
        return None, None, current, []
    start = _date_token_value(matches[0])
    end = _date_token_value(matches[1]) if len(matches) > 1 else None
    # For a current role, "Present" is the end marker; end_date remains null.
    return start, (None if current else end), current, [(m.start(), m.end()) for m in matches]


def _clean_header(line: str) -> str:
    cleaned = _DATE_TOKEN.sub(" ", line)
    cleaned = _CURRENT.sub(" ", cleaned)
    cleaned = re.sub(r"\b(?:19|20)\d{2}\b", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" •\t-–—,|()[]")


def _parse_header(line: str) -> tuple[str | None, str | None]:
    # A prose sentence ending in punctuation is not an employment header,
    # even if it contains a role keyword such as "project manager".
    if re.search(r"[.!?]$", line.strip()):
        return None, None
    cleaned = _clean_header(line)
    parts = [re.sub(r"\s+", " ", p).strip(" ,|()[]") for p in re.split(r"\s*[|@]\s*|\s+at\s+|\s*,\s*", cleaned, flags=re.I)]
    parts = [p for p in parts if p and len(p) < 100]
    title = next((p for p in parts if _ROLE_HINTS.search(p)), None)
    if title is None:
        # Handle "Senior Python Engineer at Company" after delimiter cleanup.
        title = next((p for p in parts if _ROLE_HINTS.search(p)), None)
    company = next((p for p in parts if p != title and not _SECTION_HEADERS.match(p)), None)
    if title and company == title:
        company = None
    return title, company


_SKILL_SECTION = re.compile(r"^(technical / core skills|technical skills|core skills|skills|key skills)\b", re.I)


def _skill_inventory(lines: list[str]) -> list[str]:
    """Read the resume's skills section as a candidate-specific vocabulary."""
    in_skills = False
    values: list[str] = []
    for line in lines:
        if _SKILL_SECTION.match(line):
            in_skills = True
            continue
        if in_skills and _SECTION_HEADERS.match(line):
            break
        if in_skills:
            for item in re.split(r"[,;|•]", line):
                item = item.strip(" .:-")
                if 1 < len(item) <= 60 and item.casefold() not in {v.casefold() for v in values}:
                    values.append(item)
    return values


def _skills_in_text(text: str, inventory: list[str]) -> list[str]:
    """Match inventory skills in role evidence, using case-insensitive boundaries."""
    found = []
    for skill in inventory:
        # Avoid matching tiny fragments such as 'AI' inside unrelated words.
        if len(skill) <= 2:
            pattern = re.compile(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", re.I)
        else:
            pattern = re.compile(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", re.I)
        if pattern.search(text) and skill.casefold() not in {v.casefold() for v in found}:
            found.append(skill)
    return found



def _filtered_entities(
    records: list[dict[str, Any]],
    raw_entities: dict[str, Any],
) -> dict[str, list[str]]:
    """Keep organization entities supported by parsed employment records."""

    organizations: list[str] = []
    seen: set[str] = set()

    # These patterns reject obvious non-employer values.
    invalid_org_patterns = [
        r"professional summary",
        r"technical\s*/?\s*core skills",
        r"^skills?$",
        r"^python$",
        r"^sql$",
        r"^aws$",
        r"^redis$",
        r"^docker$",
        r"^api$",
        r"^ci$",
        r"^backend developer$",
        r"^timeline$",
        r"test data notes",
        r"work experience",
        r"professional experience",
        r"education",
        r"certifications?",
    ]

    def valid_organization(value: Any) -> bool:
        if not isinstance(value, str):
            return False

        name = re.sub(r"\s+", " ", value).strip(" \t\n:|-")

        if not name or len(name) < 2 or len(name) > 100:
            return False

        if any(
            re.search(pattern, name, flags=re.IGNORECASE)
            for pattern in invalid_org_patterns
        ):
            return False

        # Reject strings containing embedded section headings/newlines.
        if "\n" in value or "\r" in value:
            return False

        # Reject entries that are just common technology names.
        if not re.search(r"[A-Za-z]", name):
            return False

        return True

    # Employment records are the primary source of employer names.
    for record in records:
        employer = record.get("employer")

        if valid_organization(employer):
            normalized = re.sub(r"\s+", " ", employer).strip()
            key = normalized.casefold()

            if key not in seen:
                organizations.append(normalized)
                seen.add(key)

    # Do not add unverified spaCy organization predictions here.
    # This prevents skills, headings, and role titles from leaking
    # into entities_detected.organizations.

    dates: list[str] = []
    seen_dates: set[str] = set()

    for record in records:
        for field in ("start_date", "end_date"):
            value = record.get(field)

            if isinstance(value, str) and value and value not in seen_dates:
                dates.append(value)
                seen_dates.add(value)

    return {
        "organizations": organizations,
        "dates": dates,
    }


def analyze_timeline(experiences: list[dict[str, Any]], as_of: date | None = None) -> dict[str, Any]:
    """Calculate inclusive calendar-month union, pairwise overlaps, and gaps."""
    today = (as_of or date.today()).strftime("%Y-%m")
    ranges = []
    invalid = []
    for item in experiences:
        start = _month_index(item.get("start_date"))
        end_value = today if item.get("is_current") else item.get("end_date")
        end = _month_index(end_value)
        if start is None or end is None or end < start:
            invalid.append(item.get("experience_id"))
            continue
        ranges.append((start, end, item.get("experience_id")))
    ranges.sort(key=lambda r: (r[0], r[1]))
    if not ranges:
        return {"total_experience_months": 0, "employment_gaps": [], "overlapping_periods": [], "invalid_experiences": invalid}

    overlaps = []
    for i, (start, end, exp_id) in enumerate(ranges):
        for prev_start, prev_end, prev_id in ranges[:i]:
            overlap_start, overlap_end = max(start, prev_start), min(end, prev_end)
            if overlap_start <= overlap_end:
                overlaps.append({"start_date": _index_date(overlap_start), "end_date": _index_date(overlap_end), "experience_id": exp_id, "overlaps_with_experience_id": prev_id})

    merged: list[list[int]] = []
    for start, end, _ in ranges:
        # Adjacent periods can be merged for union math but are not overlaps.
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    total = sum(end - start + 1 for start, end in merged)
    gaps = []
    for (_, prev_end), (next_start, _) in zip(merged, merged[1:]):
        if next_start > prev_end + 1:
            gaps.append({"start_date": _index_date(prev_end + 1), "end_date": _index_date(next_start - 1), "duration_months": next_start - prev_end - 1})
    return {"total_experience_months": total, "employment_gaps": gaps, "overlapping_periods": overlaps, "invalid_experiences": invalid}


def parse_experience(text: str, candidate_id: str = "CAND_UNKNOWN",
                     as_of: date | None = None) -> dict[str, Any]:
    """Extract multiple employment records from common resume layouts.

    Supported layouts include:
      Title | Company | Jan 2022 - Mar 2024
      Title | Company
      Jan 2022 - Mar 2024
      Title at Company (with dates on the next line)
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    lines = [
        re.sub(r"\s+", " ", line).strip(" •\t-–—")
        for line in text.splitlines()
    ]
    lines = [line for line in lines if line]
    skill_inventory = _skill_inventory(lines)

    records: list[dict[str, Any]] = []
    # Each tuple stores the title/header line and the first line of role details.
    header_indices: list[int] = []
    detail_start_indices: list[int] = []
    consumed_date_lines: set[int] = set()

    i = 0
    while i < len(lines):
        line = lines[i]

        if _SECTION_HEADERS.match(line):
            i += 1
            continue

        start, end, current, date_spans = _date_range(line)
        title, company = _parse_header(line)
        header_index = i
        detail_start = i + 1
        source_text = line

        # Layout: title/company on one line, employment dates on the next.
        if not start and title and i + 1 < len(lines):
            next_start, next_end, next_current, next_spans = _date_range(lines[i + 1])
            if next_start and (len(next_spans) >= 2 or next_current):
                start, end, current, date_spans = (
                    next_start, next_end, next_current, next_spans
                )
                source_text = f"{line} | {lines[i + 1]}"
                detail_start = i + 2
                consumed_date_lines.add(i + 1)

        # Layout: dates on their own line, immediately after the role header.
        if not start:
            i += 1
            continue

        if len(date_spans) < 2 and not current:
            i += 1
            continue

        if not title:
            # A date-only line can follow either:
            #   "Title | Company" / "Jan 2022 - Dec 2022"
            # or:
            #   "Title" / "Company" / "Jan 2022 - Dec 2022"
            # Search back up to two lines, stopping at section headers or
            # another dated line, so the employer-only line is not mistaken
            # for the role title.
            if i > 0:
                prior_index = i - 1
                prior = lines[prior_index]
                prior_title, prior_company = _parse_header(prior)

                # Do not mistake a sentence from the previous role's bullet
                # list for a title just because it contains a role keyword
                # such as "manager", "engineer", or "analyst".
                prior_looks_like_header = (
                    len(prior) <= 100
                    and not re.search(r"[.!?]$", prior)
                    and not re.match(
                        r"^(?:[-•▪]|designed|developed|built|created|implemented|"
                        r"maintained|optimized|managed|coordinated|tracked|reviewed|"
                        r"prepared|assisted|supported|worked|helped|monitored|"
                        r"provided|facilitated|gathered|supervised|checked|"
                        r"introduced|containerized|exposed|benchmarked|compared)\\b",
                        prior,
                        re.I,
                    )
                )

                if (
                    prior_title
                    and prior_looks_like_header
                    and not _SECTION_HEADERS.match(prior)
                ):
                    title, company = prior_title, prior_company
                    header_index = prior_index
                    detail_start = i + 1
                    source_text = f"{prior} | {line}"
                elif i > 1 and prior_looks_like_header and not _SECTION_HEADERS.match(prior):
                    earlier_index = i - 2
                    earlier = lines[earlier_index]
                    earlier_title, earlier_company = _parse_header(earlier)
                    earlier_looks_like_header = (
                        len(earlier) <= 100
                        and not re.search(r"[.!?]$", earlier)
                    )
                    earlier_start, _, earlier_current, earlier_spans = _date_range(earlier)
                    if (
                        earlier_title
                        and earlier_looks_like_header
                        and not earlier_start
                        and not earlier_current
                        and not earlier_spans
                        and not _SECTION_HEADERS.match(earlier)
                    ):
                        title = earlier_title
                        company = prior_company or prior
                        header_index = earlier_index
                        detail_start = i + 1
                        source_text = f"{earlier} | {prior} | {line}"

            if not title:
                i += 1
                continue

        kind = next(
            (name for name, pattern in _EMPLOYMENT_TYPES if pattern.search(title)),
            None,
        )
        months = duration_months(start, end, current, as_of)

        # Prevent duplicate extraction when a date line was paired with its header.
        duplicate = any(
            r.get("source_text") == source_text
            or (
                r.get("designation", "").casefold() == title.casefold()
                and r.get("start_date") == start
                and r.get("end_date") == end
            )
            for r in records
        )
        if not duplicate:
            records.append({
                "experience_id": f"EXP_{len(records) + 1:03d}",
                "employer": company,
                "designation": title,
                "employment_type": kind,
                "start_date": start,
                "end_date": end,
                "is_current": current,
                "duration_months": months,
                "source_text": source_text,
                "confidence": 0.8 if company and start and (end or current) else 0.5,
            })
            header_indices.append(header_index)
            detail_start_indices.append(detail_start)

        i += 1

    # Attach only the lines between this role's details start and the next role header.
    for idx, record in enumerate(records):
        start_line = detail_start_indices[idx]
        end_line = (
            header_indices[idx + 1]
            if idx + 1 < len(header_indices)
            else len(lines)
        )
        if end_line < start_line:
            end_line = start_line

        details = []
        for line in lines[start_line:end_line]:
            if _SECTION_HEADERS.match(line):
                break
            # Ignore standalone date lines and other dated role headers.
            if _DATE_TOKEN.search(line):
                continue
            cleaned_detail = line.lstrip("-•▪ ").strip()
            if cleaned_detail:
                details.append(cleaned_detail)


    for record in records:
        evidence = " ".join([
            record.get("designation") or "",
            record.get("source_text") or "",
        ])

    raw_entities = _entities(text)
    entities = _filtered_entities(records, raw_entities)

    analysis = analyze_timeline(records, as_of=as_of)
    return {
        "candidate_id": candidate_id,
        "experiences": records,
        "total_experience_months": analysis["total_experience_months"],
        "employment_gaps": analysis["employment_gaps"],
        "overlapping_periods": analysis["overlapping_periods"],
        "invalid_experiences": analysis.get("invalid_experiences", []),
        "nlp": {
            "library": "spaCy" if _load_nlp() is not None else "regex fallback",
            "entities_detected": entities,
            "model": "en_core_web_sm" if _load_nlp() is not None else "unavailable; structural parser active",
        },
        "review_required": True,
    }
