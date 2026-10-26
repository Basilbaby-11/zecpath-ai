"""Create a scoring copy with unnecessary direct identifiers removed/redacted."""
from __future__ import annotations
import copy, re
from typing import Any, Mapping

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)")
# Avoid treating common YYYY-MM / YYYY-MM - YYYY-MM employment ranges as phone numbers.
DATE_RANGE_RE = re.compile(r"\b(?:19|20)\d{2}[-/](?:0?[1-9]|1[0-2])\b")
DOB_RE = re.compile(r"\b(?:date of birth|dob|born on)\s*[:\-]?\s*[^\n,;]+", re.I)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        value = EMAIL_RE.sub("[EMAIL_REDACTED]", value)
        def redact_phone(match: re.Match[str]) -> str:
            candidate = match.group(0)
            # Phone-like regexes can span date ranges such as 2021-01 - 2024-01.
            if DATE_RANGE_RE.search(candidate):
                return candidate
            digits = re.sub(r"\D", "", candidate)
            # Typical phone numbers contain 9–15 digits; short numeric strings are not phones.
            if not 9 <= len(digits) <= 15:
                return candidate
            return "[PHONE_REDACTED]"
        value = PHONE_RE.sub(redact_phone, value)
        return DOB_RE.sub("[DOB_REDACTED]", value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def mask_personal_attributes(resume: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied scoring view; the input record remains unchanged.

    Names/contact/location fields are removed from the scoring view. This is a
    risk-reduction step, not proof that indirect or proxy bias has been removed.
    Keep the original-to-candidate-ID mapping separately with access controls.
    """
    result = copy.deepcopy(dict(resume))
    for key in ("personal_info", "candidate_identity", "contact", "photo", "date_of_birth", "dob", "gender", "marital_status", "full_name", "name", "email", "phone", "address"):
        result.pop(key, None)
    candidate = result.get("candidate")
    if isinstance(candidate, dict):
        for key in ("full_name", "name", "email", "phone", "location", "date_of_birth", "dob", "gender", "marital_status", "photo", "address"):
            candidate.pop(key, None)
    # Redact direct identifiers that may have leaked into free-text fields.
    return _redact(result)
