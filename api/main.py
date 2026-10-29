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
    role: str | None = Field(default=None, max_length=255)
    # Existing ats_scoring_engine scores component outputs; it does not extract them.
    component_scores: dict[str, float]

    @model_validator(mode="after")
    def validate_components(self):
        if not self.component_scores:
            raise ValueError("component_scores cannot be empty")
        for name, score in self.component_scores.items():
            if not 0 <= score <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
        return self


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


def parse_resume_adapter(resume_record: dict[str, Any]) -> dict[str, Any]:
    """Use the real parsers.resume_extractor.extract_one(Path) function."""
    from parsers.resume_extractor import extract_one

    result = extract_one(Path(resume_record["path"]))
    if result.get("status") != "success":
        raise ValueError(result.get("error", "Resume extraction failed."))
    # Keep the API response structured and avoid returning raw resume text.
    profile = {
        "candidate_id": result.get("candidate_id") or resume_record["candidate_id"],
        "name": result.get("name"),
        "email": result.get("email"),
        "phone": result.get("phone"),
        "skills": result.get("skills", []),
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "source_document": result.get("source_document"),
        "file_type": result.get("file_type"),
        "extraction_status": "success",
        "note": "The current extract_one pipeline extracts basic identity fields and skills; section-level fields are not provided by this function.",
    }
    resume_record["parsed_profile"] = profile
    resume_record["status"] = "completed"
    return {"resume_id": resume_record["resume_id"], "candidate_id": resume_record["candidate_id"], "parsed_profile": profile}


def score_adapter(candidate_id: str, payload: ScoreRequest) -> dict[str, Any]:
    """Call the repository's configured weighted ATS scoring engine."""
    from scoring.ats_scoring_engine import load_weight_config, score_candidate

    config_path = Path("config/ats_scoring_weights.json")
    weight_config = load_weight_config(config_path) if config_path.is_file() else load_weight_config()
    result = score_candidate(
        payload.component_scores,
        candidate_id=candidate_id,
        job_id=payload.job_id,
        role=payload.role,
        weight_config=weight_config,
    )
    return result


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


@app.post(f"{API_PREFIX}/resumes", status_code=202)
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: str = Form(..., min_length=1),
    job_id: str | None = Form(default=None),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(400, detail={"code": "INVALID_RESUME_FORMAT", "message": "Only PDF and DOCX files are supported."})
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
    asyncio.create_task(run_task(task_id, score_adapter, candidate_id, payload))
    return {"task_id": task_id, "candidate_id": candidate_id, "job_id": payload.job_id, "status": "queued"}


@app.post(f"{API_PREFIX}/jobs/{{job_id}}/shortlist", status_code=202)
async def shortlist(job_id: str, payload: ShortlistRequest):
    task_id = create_task("shortlist", job_id=job_id)
    asyncio.create_task(run_task(task_id, build_shortlist, job_id, payload))
    return {"task_id": task_id, "job_id": job_id, "status": "queued"}


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
