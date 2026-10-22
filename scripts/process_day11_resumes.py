"""Batch-process DOCX resumes with the Day 11 spaCy NLP parser.

Run from repository root:
    python scripts/process_day11_resumes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parsers.resume_extractor import read_docx
from parsers.education_certification_parser import parse_education_and_certifications

INPUT_DIR = ROOT / "data" / "sample_resumes_with_Experience"
OUTPUT_DIR = ROOT / "data" / "day11_education_outputs"

from ats_engine.education_relevance_engine import score_education_relevance

def main() -> int:
    files = sorted(INPUT_DIR.glob("*.docx"))
    if not files:
        print(f"No DOCX resumes found in: {INPUT_DIR}")
        return 1
    JOB_PROFILE_PATH = ROOT / "data" / "parsed_job_descriptions" / "job_jd_01_junior_python_developer_32bde52ee2.json"

    job_profile = json.loads(
        JOB_PROFILE_PATH.read_text(encoding="utf-8")
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for path in files:
        try:
            text = read_docx(path)
            profile = parse_education_and_certifications(text)

            relevance = score_education_relevance(
                education=profile.get("education", []),
                certifications=profile.get("certifications", []),
                job_profile=job_profile,
            )

            result = {
                "source_document": path.name,
                "status": "success",
                **profile,
                "education_relevance": relevance,
            }
            out_path = OUTPUT_DIR / f"{path.stem}_education.json"
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"SUCCESS: {path.name} -> {out_path.name} | education={len(profile['education'])}, certifications={len(profile['certifications'])}")
        except Exception as exc:  # Keep processing the remaining resumes.
            result = {"source_document": path.name, "status": "failed", "error": str(exc)}
            print(f"FAILED: {path.name}: {exc}")
        results.append(result)

    summary = {
        "total_resumes": len(results),
        "successful": sum(item["status"] == "success" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    summary_path = OUTPUT_DIR / "day11_batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n--- Day 11 batch summary ---")
    print(f"Total: {summary['total_resumes']} | Successful: {summary['successful']} | Failed: {summary['failed']}")
    print(f"Outputs: {OUTPUT_DIR}")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
