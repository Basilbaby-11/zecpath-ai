"""Generate ranked and shortlisted candidate output from Day 13 ATS results."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUT_DIR = ROOT / "data" / "ats_scores"
OUTPUT_DIR = ROOT / "data" / "ranked_candidates"
THRESHOLDS_FILE = ROOT / "config" / "shortlisting_thresholds.json"

INPUT_FILE = INPUT_DIR / "ats_scoring_results.json"
OUTPUT_FILE = OUTPUT_DIR / "ranked_candidates.json"

from ranking.candidate_ranking_engine import rank_candidates
from shortlisting.shortlisting_engine import classify_candidate, validate_thresholds
from reports.recruiter_report_generator import generate_recruiter_reports


def read_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=INPUT_FILE,help="Day 13 ATS scoring results JSON")
    parser.add_argument("--thresholds",type=Path,default=THRESHOLDS_FILE,help="Shortlisting threshold configuration")
    parser.add_argument("--output",type=Path,default=OUTPUT_FILE,help="Output ranked candidate JSON")
    args = parser.parse_args()

    source = read_json(args.input)
    if isinstance(source, dict):
        results = source.get("results")
    else:
        results = source
    if not isinstance(results, list):
        parser.error("Input must be a list or an object containing a 'results' list.")
    thresholds = validate_thresholds(read_json(args.thresholds))
    ranked = rank_candidates(results)
    classified = [classify_candidate(row, thresholds) for row in ranked]

    by_job = {}
    for row in classified:
        job_id = str(row.get("job_id") or "unknown_job")
        bucket = by_job.setdefault(job_id, {
            "job_id": row.get("job_id"),
            "role": row.get("role"),
            "candidate_count": 0,
            "shortlisted": [],
            "review": [],
            "rejected": [],
        })
        bucket["candidate_count"] += 1
        status = row["shortlisting_status"]
        bucket[status].append(row)

    payload = {
        "engine_version": "1.0.0",
        "pipeline": "day14_candidate_ranking_shortlisting",
        "input_candidate_count": len(results),
        "ranked_candidate_count": len(classified),
        "thresholds": thresholds,
        "summary": {
            "shortlisted": sum(r["shortlisting_status"] == "shortlisted" for r in classified),
            "review": sum(r["shortlisting_status"] == "review" for r in classified),
            "rejected": sum(r["shortlisting_status"] == "rejected" for r in classified),
            "missing_score": sum(r.get("overall_score") is None for r in classified),
        },
        "results": classified,
        "by_job": by_job,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    REPORTS_DIR = ROOT / "data" / "recruiter_reports"

    report_summary = generate_recruiter_reports(
        payload=payload,
        output_dir=REPORTS_DIR,
        top_n=5
    )

    print("Recruiter reports generated successfully")
    print(report_summary)
    print(f"Input candidates: {len(results)}")
    print(f"Shortlisted: {payload['summary']['shortlisted']}")
    print(f"Review: {payload['summary']['review']}")
    print(f"Rejected: {payload['summary']['rejected']}")
    print(f"Output: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
