"""Run semantic matching for every resume JSON against every JD JSON.

From the repository root:
    python scripts/run_semantic_matching_batch.py

Optional custom paths:
    python scripts/run_semantic_matching_batch.py --resume-dir data/combined_resume_outputs --jd-dir data/parsed_job_descriptions --output-dir data/semantic_matching_outputs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ats_engine.semantic_matching_engine import SemanticMatchingEngine  # noqa: E402


def read_json_records(path: Path) -> list[dict[str, Any]]:
    """Read one JSON file and return record dictionaries from common JSON shapes."""
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WARN] Skipping {path}: {exc}", file=sys.stderr)
        return []

    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        # Common combined-output wrappers used by extraction pipelines.
        for key in ("resumes", "resume_records", "candidates", "job_descriptions", "jobs", "records", "results", "data"):
            if isinstance(payload.get(key), list):
                values = payload[key]
                break
        else:
            values = [payload]
    else:
        print(f"[WARN] Skipping {path}: JSON root must be an object or list", file=sys.stderr)
        return []

    records: list[dict[str, Any]] = []
    for i, item in enumerate(values, start=1):
        if isinstance(item, dict):
            # Keep parser data intact; attach an ID only if one is absent.
            record = dict(item)
            record.setdefault("_source_file", path.name)
            records.append(record)
        else:
            print(f"[WARN] Skipping non-object record #{i} in {path}", file=sys.stderr)
    return records


def collect_records(folder: Path) -> list[dict[str, Any]]:
    if not folder.exists():
        raise FileNotFoundError(f"Input folder does not exist: {folder}")
    files = sorted(p for p in folder.rglob("*.json") if p.is_file())
    if not files:
        raise FileNotFoundError(f"No .json files found in: {folder}")
    all_records: list[dict[str, Any]] = []
    for path in files:
        for index, record in enumerate(read_json_records(path), start=1):
            record.setdefault("_record_index", index)
            all_records.append(record)
    return all_records


def stable_id(record: dict[str, Any], keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch semantic matching for resume and JD JSON folders.")
    parser.add_argument("--resume-dir", default="data/combined_resume_outputs", help="Folder containing combined resume JSON files")
    parser.add_argument("--jd-dir", default="data/parsed_job_descriptions", help="Folder containing parsed JD JSON files")
    parser.add_argument("--output-dir", default="data/semantic_matching_outputs", help="Folder for matching result JSON files")
    parser.add_argument("--strong-threshold", type=float, default=0.75)
    parser.add_argument("--moderate-threshold", type=float, default=0.55)
    args = parser.parse_args()

    def resolve(path_string: str) -> Path:
        path = Path(path_string)
        return path if path.is_absolute() else ROOT / path

    resume_dir, jd_dir, output_dir = map(resolve, (args.resume_dir, args.jd_dir, args.output_dir))
    try:
        resumes = collect_records(resume_dir)
        jobs = collect_records(jd_dir)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    # One model instance is reused across all comparisons.
    engine = SemanticMatchingEngine(
        strong_threshold=args.strong_threshold,
        moderate_threshold=args.moderate_threshold,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    total = len(resumes) * len(jobs)
    print(f"Loaded {len(resumes)} resume record(s) and {len(jobs)} job description record(s).")
    print(f"Scoring {total} resume/JD pair(s). The first run may download the embedding model.")

    for ri, resume in enumerate(resumes, start=1):
        resume_id = stable_id(resume, ("resume_id", "candidate_id", "id"), f"RES-{ri:04d}")
        for ji, job in enumerate(jobs, start=1):
            job_id = stable_id(job, ("job_id", "jd_id", "job_description_id", "id"), f"JD-{ji:04d}")
            try:
                result = engine.compare(resume, job, resume_id=resume_id, job_id=job_id)
            except Exception as exc:
                print(f"[WARN] Failed pair {resume_id} vs {job_id}: {exc}", file=sys.stderr)
                result = {
                    "resume_id": resume_id,
                    "job_id": job_id,
                    "status": "error",
                    "error": str(exc),
                }
            result["resume_source_file"] = resume.get("_source_file")
            result["job_source_file"] = job.get("_source_file")
            results.append(result)

    output_path = output_dir / "semantic_matching_results.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({
            "input_resume_count": len(resumes),
            "input_job_description_count": len(jobs),
            "pair_count": total,
            "successful_count": sum(1 for x in results if x.get("method")),
            "error_count": sum(1 for x in results if x.get("status") == "error"),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    # A compact CSV-friendly JSONL file is also useful for review.
    summary_path = output_dir / "semantic_matching_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump([
            {
                "resume_id": x.get("resume_id"),
                "job_id": x.get("job_id"),
                "overall_score": x.get("overall_score"),
                "overall_category": x.get("overall_category"),
                "status": x.get("status", "scored" if x.get("method") else "error"),
            }
            for x in results
        ], f, ensure_ascii=False, indent=2)

    print(f"Saved full results: {output_path}")
    print(f"Saved summary:      {summary_path}")
    print("Note: similarity scores are ranking signals, not hiring probabilities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
