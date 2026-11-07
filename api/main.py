"""Day 16 REST API integration for the existing Zecpath AI modules.

Development prototype: asynchronous tasks/results are in memory and disappear
on restart. Use only trusted local test data until durable task storage,
authentication and production deployment controls are added.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

API_PREFIX = "/api/v1"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("ZECPATH_UPLOAD_DIR", "data/api_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("zecpath.api")

app = FastAPI(
    title="Zecpath ATS AI API",
    version="1.0.0",
    description="REST API for the existing Zecpath resume extraction, ATS scoring, ranking and shortlisting modules.",
)

RESUMES: dict[str, dict[str, Any]] = {}
TASKS: dict[str, dict[str, Any]] = {}
JOB_RANKINGS: dict[str, dict[str, Any]] = {}
CANDIDATE_SCORES: dict[tuple[str, str], dict[str, Any]] = {}
JOBS: dict[str, dict[str, Any]] = {}

# Local development origins only. Restrict this list to the deployed UI origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def error_body(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or new_id("req")
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_id=%s unexpected_error", request_id)
        response = JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
        )
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id, request.method, request.url.path, response.status_code,
        (time.perf_counter() - start) * 1000,
    )
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None) or new_id("req")
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    elif isinstance(exc.detail, dict) and "code" in exc.detail:
        body = {"error": {**exc.detail, "request_id": request_id}}
    else:
        body = error_body("HTTP_ERROR", str(exc.detail), request_id)
    return JSONResponse(status_code=exc.status_code, content=body, headers={"X-Request-ID": request_id})


class ScoreRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=128)


class JobCreateRequest(BaseModel):
    job_id: str | None = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=30, max_length=50000)



class ShortlistCandidate(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=128)
    overall_score: float | None = Field(default=None, ge=0, le=100)


class ShortlistRequest(BaseModel):
    candidates: list[ShortlistCandidate] = Field(min_length=1)
    top_n: int = Field(default=5, ge=1, le=1000)
    shortlist_threshold: float = Field(default=75.0, ge=0, le=100)
    review_threshold: float = Field(default=50.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.review_threshold > self.shortlist_threshold:
            raise ValueError("review_threshold must be <= shortlist_threshold")
        return self


def _score_from_text(candidate_id: str, job_id: str, resume_text: str,
                     resume_profile: dict[str, Any]) -> dict[str, Any]:
    """Use the shared component pipeline and existing weighted ATS scorer."""
    from ats_engine.candidate_scoring_pipeline import generate_candidate_score

    job_record = JOBS.get(job_id)
    if not job_record:
        raise ValueError(f"Job description '{job_id}' is not configured.")
    return generate_candidate_score(
        candidate_id=candidate_id,
        job_id=job_id,
        resume_profile=resume_profile,
        job=job_record["parsed"],
        job_description=job_record.get("description", ""),
        resume_text=resume_text,
    )


def parse_resume_adapter(resume_record: dict[str, Any]) -> dict[str, Any]:
    """Extract full resume text, parse existing profile modules and score against its selected JD."""
    from parsers.resume_extractor import extract_resume, extract_one
    from parsers.skill_ner import extract_skill_entities
    from parsers.experience_parser import parse_experience
    from parsers.education_certification_parser import parse_education_and_certifications

    extracted = extract_resume(Path(resume_record["path"]))
    text = extracted["extracted_text"]
    basic = extract_one(Path(resume_record["path"]))
    skills = extract_skill_entities(text)
    experience = parse_experience(text, candidate_id=resume_record["candidate_id"])
    education = parse_education_and_certifications(text)
    profile = {
        "candidate_id": resume_record["candidate_id"], "name": basic.get("name"),
        "email": basic.get("email"), "phone": basic.get("phone"),
        "skills": [x.get("name") for x in skills], "skill_entities": skills,
        "education": education.get("education", []),
        "experience": experience.get("experiences", experience.get("experience", [])),
        # Use the experience parser's overlap-aware aggregate; do not sum role durations here.
        "total_experience_months": experience.get("total_experience_months"),
        "certifications": education.get("certifications", []),
        "source_document": extracted.get("source_document"),
        "file_type": extracted.get("file_type"), "extraction_status": "success",
    }
    resume_record["parsed_profile"] = profile
    resume_record["extracted_text"] = text
    resume_record["status"] = "completed"
    result = {"resume_id": resume_record["resume_id"], "candidate_id": resume_record["candidate_id"],
              "parsed_profile": profile}
    job_id = resume_record.get("job_id")
    if job_id and job_id in JOBS:
        score = _score_from_text(resume_record["candidate_id"], job_id, text, profile)
        CANDIDATE_SCORES[(resume_record["candidate_id"], job_id)] = score
        result["score"] = score
    return result


def score_adapter(candidate_id: str, payload: ScoreRequest) -> dict[str, Any]:
    """Generate a fresh ATS score from the stored resume and saved JD."""
    matches = [r for r in RESUMES.values()
               if r.get("candidate_id") == candidate_id and r.get("job_id") == payload.job_id
               and r.get("extracted_text")]
    if not matches:
        raise ValueError("No parsed resume is available for this candidate and job. Upload the resume first.")
    resume_record = max(matches, key=lambda r: r.get("created_at", ""))
    return _score_from_text(candidate_id, payload.job_id, resume_record["extracted_text"],
                            resume_record.get("parsed_profile") or {})


def score_and_store(candidate_id: str, payload: ScoreRequest) -> dict[str, Any]:
    result = score_adapter(candidate_id, payload)
    CANDIDATE_SCORES[(candidate_id, payload.job_id)] = result
    return result


def list_candidate_records() -> list[dict[str, Any]]:
    """Return candidate records created by successful resume parsing."""
    latest: dict[str, dict[str, Any]] = {}
    for resume in RESUMES.values():
        profile = resume.get("parsed_profile")
        if not profile:
            continue
        candidate_id = resume["candidate_id"]
        score = CANDIDATE_SCORES.get((candidate_id, resume.get("job_id") or ""))
        latest[candidate_id] = {
            "candidate_id": candidate_id,
            "name": profile.get("name") or candidate_id,
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "skills": profile.get("skills", []),
            "job_id": resume.get("job_id"),
            "job_title": (JOBS.get(resume.get("job_id") or "", {}).get("parsed", {}).get("title") or resume.get("job_id")),
            "resume_id": resume["resume_id"],
            "filename": resume.get("filename"),
            "created_at": resume.get("created_at"),
            "status": "scored" if score else "parsed",
            "overall_score": score.get("overall_score") if score else None,
            "extraction_status": profile.get("extraction_status"),
        }
    return sorted(latest.values(), key=lambda row: row.get("created_at") or "", reverse=True)


def build_shortlist(job_id: str, payload: ShortlistRequest) -> dict[str, Any]:
    """Call existing ranking and shortlisting engines rather than reimplementing them."""
    from ranking.candidate_ranking_engine import rank_candidates
    from shortlisting.shortlisting_engine import classify_candidate

    rows = [
        {"candidate_id": candidate.candidate_id, "job_id": job_id, "overall_score": candidate.overall_score}
        for candidate in payload.candidates
    ]
    ranked = rank_candidates(rows)
    classified = [
        classify_candidate(
            row,
            {"shortlist_min": payload.shortlist_threshold, "review_min": payload.review_threshold},
        )
        for row in ranked
    ]
    # Put scored candidates first; keep missing-score records for manual review at the end.
    classified.sort(key=lambda row: (
        row.get("overall_score") is None,
        -(row.get("overall_score") if row.get("overall_score") is not None else 0),
        row.get("candidate_id", ""),
    ))
    selected = classified[:payload.top_n]
    # Recompute display ranks after top_n selection; preserve engine status/reason.
    for index, row in enumerate(selected, start=1):
        row["rank"] = index if row.get("overall_score") is not None else None
    result = {
        "job_id": job_id,
        "status": "completed",
        "count": len(selected),
        "ranked_candidates": selected,
        "decision_policy": {
            "shortlist_threshold": payload.shortlist_threshold,
            "review_threshold": payload.review_threshold,
            "human_review_required": True,
        },
    }
    JOB_RANKINGS[job_id] = result
    return result


async def run_task(task_id: str, operation, *args):
    task = TASKS[task_id]
    task["status"] = "processing"
    task["updated_at"] = now_iso()
    try:
        result = await asyncio.to_thread(operation, *args)
        task["status"] = "completed"
        task["result"] = result
        task["error"] = None
    except Exception as exc:
        logger.exception("task_id=%s operation_failed", task_id)
        task["status"] = "failed"
        task["result"] = None
        # Do not expose exception strings that may contain local paths or personal data.
        task["error"] = {"code": "PROCESSING_FAILED", "message": "The task could not be completed."}
    finally:
        task["updated_at"] = now_iso()


def create_task(operation: str, **metadata) -> str:
    task_id = new_id("task")
    TASKS[task_id] = {
        "task_id": task_id, "operation": operation, "status": "queued",
        "result": None, "error": None, "created_at": now_iso(),
        "updated_at": now_iso(), **metadata,
    }
    return task_id


@app.get("/")
async def root():
    return {"service": "zecpath-ats-api", "version": app.version, "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "zecpath-ats-api", "version": app.version}


@app.get(f"{API_PREFIX}/jobs")
async def get_jobs():
    return {"count": len(JOBS), "jobs": [
        {"job_id": key, "title": value["parsed"].get("title") or value["title"],
         "description": value.get("description", ""), "created_at": value.get("created_at")}
        for key, value in JOBS.items()
    ]}


@app.post(f"{API_PREFIX}/jobs")
async def create_job(payload: JobCreateRequest):
    from parsers.jd_parser import parse_job_description
    job_id = payload.job_id or new_id("JOB")
    if job_id in JOBS:
        raise HTTPException(409, detail={"code": "JOB_EXISTS", "message": "This job ID already exists."})
    parsed = parse_job_description(payload.description, file_name=f"{job_id}.txt", job_id=job_id)
    if payload.title.strip():
        parsed["title"] = payload.title.strip()
    JOBS[job_id] = {"title": payload.title.strip(), "description": payload.description,
                    "parsed": parsed, "created_at": now_iso()}
    return {"job_id": job_id, "title": parsed["title"], "parsed_job": parsed}


@app.post(f"{API_PREFIX}/jobs/upload")
async def upload_job_description(file: UploadFile = File(...), title: str = Form(...), job_id: str | None = Form(default=None)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".pdf", ".docx"}:
        raise HTTPException(400, detail={"code": "INVALID_JD_FORMAT", "message": "Only TXT, PDF and DOCX job descriptions are supported."})
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail={"code": "FILE_TOO_LARGE", "message": "Maximum upload size is 10 MB."})
    temp_id = job_id or new_id("JOB")
    temp_path = UPLOAD_DIR / f"{temp_id}{suffix}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(content)
    try:
        if suffix == ".txt":
            raw_text = content.decode("utf-8-sig")
        else:
            from parsers.resume_extractor import extract_resume
            raw_text = extract_resume(temp_path)["extracted_text"]
        request_payload = JobCreateRequest(job_id=temp_id, title=title, description=raw_text)
        return await create_job(request_payload)
    finally:
        temp_path.unlink(missing_ok=True)


@app.post(f"{API_PREFIX}/resumes", status_code=202)
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: str = Form(..., min_length=1),
    job_id: str | None = Form(default=None),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(400, detail={"code": "INVALID_RESUME_FORMAT", "message": "Only PDF and DOCX files are supported."})
    if job_id and job_id not in JOBS:
        raise HTTPException(404, detail={"code": "JOB_NOT_FOUND", "message": "Save the job description before uploading resumes for it."})
    resume_id = new_id("res")
    destination = (UPLOAD_DIR / f"{resume_id}{suffix}").resolve()
    UPLOAD_DIR.resolve().mkdir(parents=True, exist_ok=True)
    if UPLOAD_DIR.resolve() not in destination.parents:
        raise HTTPException(400, detail={"code": "INVALID_UPLOAD_PATH", "message": "Invalid upload path."})
    size = 0
    try:
        with destination.open("xb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, detail={"code": "FILE_TOO_LARGE", "message": "Maximum upload size is 10 MB."})
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    record = {
        "resume_id": resume_id, "candidate_id": candidate_id, "job_id": job_id,
        "path": str(destination), "filename": Path(file.filename or "resume").name,
        "size_bytes": size, "created_at": now_iso(), "parsed_profile": None, "status": "uploaded",
    }
    RESUMES[resume_id] = record
    task_id = create_task("parse_resume", resume_id=resume_id)
    asyncio.create_task(run_task(task_id, parse_resume_adapter, record))
    return {"resume_id": resume_id, "task_id": task_id, "status": "queued"}


@app.post(f"{API_PREFIX}/resumes/{{resume_id}}/parse", status_code=202)
async def parse_resume(resume_id: str):
    record = RESUMES.get(resume_id)
    if not record:
        raise HTTPException(404, detail={"code": "RESUME_NOT_FOUND", "message": "The requested resume does not exist."})
    task_id = create_task("parse_resume", resume_id=resume_id)
    asyncio.create_task(run_task(task_id, parse_resume_adapter, record))
    return {"resume_id": resume_id, "task_id": task_id, "status": "queued"}


@app.post(f"{API_PREFIX}/candidates/{{candidate_id}}/score", status_code=202)
async def score_candidate(candidate_id: str, payload: ScoreRequest):
    task_id = create_task("score_candidate", candidate_id=candidate_id, job_id=payload.job_id)
    asyncio.create_task(run_task(task_id, score_and_store, candidate_id, payload))
    return {"task_id": task_id, "candidate_id": candidate_id, "job_id": payload.job_id, "status": "queued"}


@app.post(f"{API_PREFIX}/jobs/{{job_id}}/shortlist", status_code=202)
async def shortlist(job_id: str, payload: ShortlistRequest):
    task_id = create_task("shortlist", job_id=job_id)
    asyncio.create_task(run_task(task_id, build_shortlist, job_id, payload))
    return {"task_id": task_id, "job_id": job_id, "status": "queued"}


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/candidates/{{candidate_id}}/eligibility")
async def get_candidate_eligibility(job_id: str, candidate_id: str):
    """Evaluate an existing ATS result against recruiter-configured job rules."""
    from eligibility.eligibility_engine import evaluate_eligibility, load_eligibility_rules

    job_record = JOBS.get(job_id)
    if not job_record:
        raise HTTPException(404, detail={"code": "JOB_NOT_FOUND", "message": "The requested job does not exist."})
    ats_result = CANDIDATE_SCORES.get((candidate_id, job_id))
    if ats_result is None:
        raise HTTPException(404, detail={"code": "ATS_SCORE_NOT_FOUND", "message": "No ATS score exists for this candidate and job."})
    profiles = [r.get("parsed_profile") for r in RESUMES.values()
                if r.get("candidate_id") == candidate_id and r.get("job_id") == job_id and r.get("parsed_profile")]
    if not profiles:
        raise HTTPException(404, detail={"code": "CANDIDATE_PROFILE_NOT_FOUND", "message": "No parsed candidate profile exists for this job."})
    config_path = Path(__file__).resolve().parents[1] / "config" / "eligibility_rules.json"
    rules = load_eligibility_rules(config_path) if config_path.is_file() else load_eligibility_rules()
    decision = evaluate_eligibility(
        candidate=profiles[-1], ats_result=ats_result,
        job={**job_record["parsed"], "job_id": job_id}, rules_config=rules,
    )
    return decision


@app.get(f"{API_PREFIX}/candidates")
async def get_candidates():
    rows = list_candidate_records()
    return {"count": len(rows), "candidates": rows, "source": "parsed_resume_records"}


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/rankings")
async def get_rankings(job_id: str):
    result = JOB_RANKINGS.get(job_id)
    if result is None:
        raise HTTPException(404, detail={"code": "RANKINGS_NOT_FOUND", "message": "No ranking result exists for this job."})
    return result


@app.get(f"{API_PREFIX}/tasks/{{task_id}}")
async def get_task(task_id: str):
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "The requested task does not exist."})
    response = dict(task)
    response.pop("operation", None)
    return response
