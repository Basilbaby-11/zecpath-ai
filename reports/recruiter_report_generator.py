"""Generate top candidate lists and recruiter-friendly reports."""

import csv
import json
from pathlib import Path


def generate_recruiter_reports(payload, output_dir: Path, top_n=5):
    if top_n < 1:
        raise ValueError("top_n must be at least 1.")

    output_dir.mkdir(parents=True, exist_ok=True)

    top_candidates = {}
    shortlisted_candidates = []
    csv_rows = []

    fieldnames = [
        "job_id",
        "role",
        "candidate_id",
        "rank",
        "ats_score",
        "skill_match",
        "experience_relevance",
        "education_alignment",
        "semantic_similarity",
        "status",
        "reason",
    ]

    for job_id, job_data in payload.get("by_job", {}).items():
        candidates = (
            job_data.get("shortlisted", [])
            + job_data.get("review", [])
            + job_data.get("rejected", [])
        )

        # Rank ascending; use ATS score descending as a fallback.
        candidates.sort(
            key=lambda c: (
                c.get("rank") is None,
                c.get("rank")
                if c.get("rank") is not None
                else float("inf"),
                -(c.get("overall_score")
                  if isinstance(c.get("overall_score"), (int, float))
                  else float("-inf")),
                str(c.get("candidate_id") or ""),
            )
        )

        top_candidates[job_id] = {
            "job_id": job_data.get("job_id", job_id),
            "role": job_data.get("role"),
            "total_candidates": len(candidates),
            "top_candidates": candidates[:top_n],
        }

        shortlisted_candidates.extend(job_data.get("shortlisted", []))

        for candidate in candidates:
            csv_rows.append({
                "job_id": job_id,
                "role": job_data.get("role"),
                "candidate_id": candidate.get("candidate_id"),
                "rank": candidate.get("rank"),
                "ats_score": candidate.get("overall_score"),
                "skill_match": candidate.get("skill_match"),
                "experience_relevance": candidate.get(
                    "experience_relevance"
                ),
                "education_alignment": candidate.get(
                    "education_alignment"
                ),
                "semantic_similarity": candidate.get(
                    "semantic_similarity"
                ),
                "status": candidate.get("shortlisting_status"),
                "reason": candidate.get("shortlisting_reason"),
            })

    with (output_dir / "top_candidates.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(top_candidates, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with (output_dir / "shortlisted_candidates.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(shortlisted_candidates, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with (output_dir / "recruiter_report.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    return {
        "jobs_processed": len(top_candidates),
        "shortlisted": len(shortlisted_candidates),
        "report_rows": len(csv_rows),
    }
