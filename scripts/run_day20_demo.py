"""Run the Day 20 synthetic ATS demo without requiring the REST API.

Usage from repository root:
    python scripts/run_day20_demo.py
"""
import json
import sys
from pathlib import Path

# Add the project root to Python's import path
ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docx import Document

from ats_engine.matcher import calculate_match_score
from parsers.skill_ner import extract_skill_entities
from scoring.ats_scoring_engine import score_candidate

DATA = ROOT / "data" / "day20_demo"
RESUMES = DATA / "resumes"
JOBS = DATA / "job_descriptions"
OUTPUT = DATA / "demo_run_results.json"
DICTIONARY = ROOT / "data" / "skill_dictionary.json"


def read_docx_text(path: Path) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def main() -> int:
    jobs = []
    for path in sorted(JOBS.glob("*.txt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        fields = {}
        for line in lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                fields[key.strip()] = value.strip()
        jobs.append({
            "job_id": fields["JOB ID"],
            "title": fields["TITLE"],
            "required_skills": [x.strip() for x in fields["REQUIRED SKILLS"].split(",") if x.strip()],
        })

    candidates = []
    for path in sorted(RESUMES.glob("*.docx")):
        text = read_docx_text(path)
        entities = extract_skill_entities(text, dictionary_path=DICTIONARY)
        skills = sorted({x["name"] for x in entities})
        candidate_id = path.stem
        candidate_results = []
        for job in jobs:
            skill_score = calculate_match_score(job["required_skills"], skills)
            score = score_candidate(
                {"skill_match": skill_score},
                candidate_id=candidate_id,
                job_id=job["job_id"],
                role=job["title"],
            )
            candidate_results.append({
                "job_id": job["job_id"],
                "job_title": job["title"],
                "detected_skills": skills,
                "skill_match_score": skill_score,
                "overall_score": score["overall_score"],
                "data_quality": score["data_quality"],
                "score_explanation": score,
            })
        candidates.append({"candidate_id": candidate_id, "job_results": candidate_results})

    rankings = {}
    for job in jobs:
        rows = []
        for candidate in candidates:
            result = next(x for x in candidate["job_results"] if x["job_id"] == job["job_id"])
            rows.append({"candidate_id": candidate["candidate_id"], "score": result["overall_score"]})
        rankings[job["job_id"]] = sorted(rows, key=lambda x: (-x["score"], x["candidate_id"]))

    result = {
        "dataset": {"candidate_count": len(candidates), "job_count": len(jobs), "synthetic": True},
        "method": "skill extraction + required-skill overlap + existing weighted scorer with one available component",
        "warning": "This demo is not a full end-to-end production workflow. Missing scoring components are intentionally excluded and remaining weights are renormalized. Scores are not hiring probabilities.",
        "candidates": candidates,
        "rankings": rankings,
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Demo complete: {len(candidates)} candidates x {len(jobs)} jobs")
    print(f"Results: {OUTPUT}")
    for job in jobs:
        top = rankings[job["job_id"]][:3]
        print(job["job_id"], "top 3:", ", ".join(f"{x['candidate_id']}={x['score']:.1f}" for x in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
