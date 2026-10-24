"""Rank ATS-scored candidates within each job."""
from __future__ import annotations
from typing import Any, Iterable

ENGINE_VERSION = "1.0.0"

def rank_candidates(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return candidates sorted by job, score descending, then candidate ID.

    Each job gets its own rank sequence. Records without a numeric score are
    retained at the bottom of that job's list and receive rank=None.
    """
    rows = [dict(row) for row in results]
    for row in rows:
        score = row.get("overall_score")
        if score is not None:
            if isinstance(score, bool):
                raise ValueError("overall_score must be numeric or null.")
            try:
                score = float(score)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid overall_score: {score!r}") from exc
            if not 0 <= score <= 100:
                raise ValueError(f"overall_score must be between 0 and 100; got {score}.")
            row["overall_score"] = round(score, 2)

    rows.sort(key=lambda r: (
        str(r.get("job_id") or ""),
        r.get("overall_score") is None,
        -(r.get("overall_score") if r.get("overall_score") is not None else 0),
        str(r.get("candidate_id") or ""),
    ))
    current_job = object()
    rank = 0
    previous_score = object()
    for row in rows:
        job_id = row.get("job_id")
        score = row.get("overall_score")
        if job_id != current_job:
            current_job, rank, previous_score = job_id, 0, object()
        if score is None:
            row["rank"] = None
        else:
            # Competition ranking: ties share a rank (1, 1, 3).
            if score != previous_score:
                rank = sum(
                    1 for prior in rows
                    if prior.get("job_id") == job_id
                    and prior.get("overall_score") is not None
                    and prior.get("overall_score") > score
                ) + 1
                previous_score = score
            row["rank"] = rank
        row["ranking_engine_version"] = ENGINE_VERSION
    return rows
