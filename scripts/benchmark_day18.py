"""Benchmark resume extraction on bundled sample files.

Usage: python scripts/benchmark_day18.py [--iterations 1] [--output reports/DAY18_BENCHMARK_RESULTS.json]
This measures local extraction latency; it does not claim production performance.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from parsers.resume_extractor import extract_resume, INPUT_DIR


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output", type=Path, default=Path("reports/DAY18_BENCHMARK_RESULTS.json"))
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    files = sorted(p for p in args.input_dir.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".docx"})
    if not files:
        parser.error(f"No PDF/DOCX resumes found in {args.input_dir}")

    results = []
    for file in files:
        durations = []
        peak_bytes = 0
        status = "success"
        word_count = 0
        error = None
        for _ in range(args.iterations):
            tracemalloc.start()
            start = time.perf_counter()
            try:
                payload = extract_resume(file)
                word_count = payload.get("word_count", 0)
            except Exception as exc:
                status, error = "failed", f"{type(exc).__name__}: {exc}"
            durations.append(time.perf_counter() - start)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak_bytes = max(peak_bytes, peak)
        results.append({
            "file": file.name,
            "status": status,
            "iterations": args.iterations,
            "latency_seconds_median": round(statistics.median(durations), 4),
            "latency_seconds_min": round(min(durations), 4),
            "peak_traced_memory_mb": round(peak_bytes / (1024 * 1024), 3),
            "word_count": word_count,
            "error": error,
        })

    payload = {
        "benchmark_type": "local_resume_extraction_microbenchmark",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": __import__("sys").version,
        "input_directory": str(args.input_dir),
        "iterations_per_file": args.iterations,
        "files_tested": len(results),
        "successful_files": sum(r["status"] == "success" for r in results),
        "failed_files": sum(r["status"] != "success" for r in results),
        "results": results,
        "limitations": ["Results depend on this machine and input files.", "tracemalloc reports Python-tracked allocations, not total process RSS.", "No baseline comparison is available unless the same inputs are benchmarked against the previous revision."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"\nSaved benchmark report: {args.output}")
    return 0 if payload["failed_files"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
