"""
Combine resume extraction, skill NER, education/certifications, and experience
into ONE JSON file for a batch of resumes.

Place this file at: zecpath-ai/scripts/combined_resume_pipeline.py
Run from the repository root:
    python scripts/combined_resume_pipeline.py
Optional:
    python scripts/combined_resume_pipeline.py --input-dir data/sample_resumes_with_Experience
    python scripts/combined_resume_pipeline.py --input-dir data/sample_resumes_with_Experience --output data/combined/all_resumes_combined.json

Supported inputs: PDF, DOCX, TXT.
Expected project modules:
    parsers/resume_extractor.py
    parsers/education_certification_parser.py
    parsers/experience_parser.py
    parsers/skill_ner.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parsers.resume_extractor import (  # noqa: E402
    clean_text,
    extract_basic_info,
    generate_candidate_id,
    read_docx,
    read_pdf,
)
from parsers.education_certification_parser import (  # noqa: E402
    parse_education_and_certifications,
)
from parsers.experience_parser import parse_experience  # noqa: E402
from parsers.skill_ner import extract_skill_entities  # noqa: E402

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def read_resume(path: Path) -> str:
    """Read a supported resume and apply the project's text cleaning."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = read_pdf(path)
    elif suffix == ".docx":
        text = read_docx(path)
    elif suffix == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported resume type: {suffix}")

    text = clean_text(text)
    if len(text.strip()) < 20 and suffix in {".pdf", ".docx"}:
        # Reuse the existing extractor's OCR fallback for scanned resumes.
        from parsers.resume_extractor import ocr_fallback
        text = clean_text(ocr_fallback(path))

    if not text.strip():
        raise ValueError("No readable text could be extracted from this resume.")
    return text


def process_one_resume(path: Path, dictionary_path: Path | None = None) -> dict[str, Any]:
    """Run all extraction modules for one resume without writing intermediate files."""
    try:
        text = read_resume(path)
        basic = extract_basic_info(text)
        candidate_id = generate_candidate_id(
            email=basic.get("email"),
            phone=basic.get("phone"),
            name=basic.get("name"),
            fallback=path.name,
        )

        education_profile = parse_education_and_certifications(text)
        experience_profile = parse_experience(text, candidate_id=candidate_id)

        # Skill NER returns detailed entity objects. The top-level skills field
        # is a deduplicated list of canonical skill names for easy downstream use.
        skill_entities = extract_skill_entities(
            text,
            dictionary_path=dictionary_path,
        )
        skills = sorted(
            {
                str(entity.get("name", "")).strip()
                for entity in skill_entities
                if entity.get("name")
            },
            key=str.casefold,
        )

        return {
            "candidate_id": candidate_id,
            "source_document": path.name,
            "status": "success",
            "personal_info": {
                "name": basic.get("name"),
                "email": basic.get("email"),
                "phone": basic.get("phone"),
            },
            "skills": skills,
            "skill_entities": skill_entities,
            "education": education_profile.get("education", []),
            "certifications": education_profile.get("certifications", []),
            "experience": experience_profile.get("experiences", []),
            "experience_analysis": {
                key: value
                for key, value in experience_profile.items()
                if key != "experiences"
            },
        }
    except Exception as exc:
        logging.exception("Failed to process resume %s", path.name)
        return {
            "candidate_id": generate_candidate_id(fallback=path.name),
            "source_document": path.name,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "personal_info": {"name": None, "email": None, "phone": None},
            "skills": [],
            "skill_entities": [],
            "education": [],
            "certifications": [],
            "experience": [],
            "experience_analysis": {},
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combine resume, skills, education, and experience into one JSON file."
    )
    parser.add_argument(
        "--input-dir",
        default=str(ROOT / "data" / "sample_resumes_with_Experience"),
        help="Folder containing PDF, DOCX, and/or TXT resumes.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "combined_resume_outputs" / "all_resumes_combined.json"),
        help="Path for the single combined JSON output.",
    )
    parser.add_argument(
        "--skill-dictionary",
        default=None,
        help="Optional path to data/skill_dictionary.json.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    dictionary_path = Path(args.skill_dictionary).expanduser().resolve() if args.skill_dictionary else None

    if not input_dir.is_dir():
        print(f"ERROR: Input folder does not exist: {input_dir}")
        return 1

    files = sorted(
        (
            path for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )
    if not files:
        print(f"No PDF, DOCX, or TXT resumes found in: {input_dir}")
        return 1

    results = [process_one_resume(path, dictionary_path) for path in files]
    successful = sum(item["status"] == "success" for item in results)
    failed = len(results) - successful

    payload = {
        "pipeline": "combined_resume_extraction",
        "total_resumes": len(results),
        "successful": successful,
        "failed": failed,
        "resumes": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n--- Combined Resume Pipeline ---")
    print(f"Input folder : {input_dir}")
    print(f"Total        : {len(results)}")
    print(f"Successful   : {successful}")
    print(f"Failed       : {failed}")
    print(f"JSON output  : {output_path}")
    if failed:
        print("\nFailed resumes:")
        for item in results:
            if item["status"] == "failed":
                print(f" - {item['source_document']}: {item['error']}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
