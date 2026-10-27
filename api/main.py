"""Day 16 FastAPI adapter for Zecpath AI.

Prototype only: local disk and in-memory task/result storage. Replace the
adapter functions with the repository's verified parser/scorer integrations
and use durable storage/queue/authentication before production.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

API_PREFIX = "/api/v1"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("ZECpath_UPLOAD_DIR", "data/api_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("zecpath.api")

app = FastAPI(
    title="Zecpath ATS AI API",
    version="1.0.0",
    description="Prototype REST adapter for resume parsing, scoring, and shortlisting.",
)

# Prototype stores. These are lost when the process restarts; use a DB and durable queue in production.
RESUMES: dict[str, dict[str, Any]] = {}
TASKS: dict[str, dict[str, Any]] = {}
JOB_RANKINGS: dict[str, dict[str, Any]] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def public_error(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or new_id("req")
    start = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id, request.method, request.url.path,
            response.status_code, (time.perf_counter() - start) * 1000,
        )
        return response
    except Exception:
        logger.exception("request_id=%s unexpected request error", request_id)
        return JSONResponse(
            status_code=500,
            content=public_error("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
            headers={"X-Request-ID": request_id},
        )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("X-Request-ID") or new_id("req")
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    else:
        body = public_error("HTTP_ERROR", str(exc.detail), request_id)
    return JSONResponse(status_code=exc.status_code, content=body, headers={"X-Request-ID": request_id})


class CandidateProfile(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)


class JobProfile(BaseModel):
    title: str = Field(min_length=1)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    description: str = ""


class ScoreRequest(BaseModel):
    job_id: str = Field(min_length=1)
    resume_id: str | None = None
    candidate_profile: CandidateProfile | None = None
    job_profile: JobProfile


class ShortlistCandidate(BaseModel):
    candidate_id: str = Field(min_length=1)
    overall_score: float = Field(ge=0, le=100)


class ShortlistRequest(BaseModel):
    candidates: list[ShortlistCandidate] = Field(min_length=1)
    top_n: int = Field(default=5, ge=1, le=1000)
    shortlist_threshold: float = Field(default=70.0, ge=0, le=100)
    review_threshold: float = Field(default=50.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.review_threshold > self.shortlist_threshold:
            raise ValueError("review_threshold must be <= shortlist_threshold")
        return self


def extract_text_from_file(file_path: Path) -> str:
    """Call the project's existing parser. Fail clearly if not integrated."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".pdf":
            from parsers.resume_extractor import extract_text_from_pdf  # type: ignore
            return str(extract_text_from_pdf(str(file_path)))
        if suffix == ".docx":
            from parsers.resume_extractor import extract_text_from_docx  # type: ignore
            return str(extract_text_from_docx(str(file_path)))
    except ImportError as exc:
        raise RuntimeError(
            "Parser adapter is not connected. Update extract_text_from_file() "
            "to call the verified function in parsers/resume_extractor.py."
        ) from exc
    except AttributeError as exc:
        raise RuntimeError(
            "The expected parser function name is not available. Check "
            "parsers/resume_extractor.py and update the adapter."
        ) from exc
    raise ValueError("Only PDF and DOCX files are supported.")


def parse_resume_adapter(resume_record: dict[str, Any]) -> dict[str, Any]:
    """Minimal adapter. Verify extraction function names against your repo before use."""
    path = Path(resume_record["path"])
    text = extract_text_from_file(path)
    # Keep extracted text internal; do not return raw resume text through the API.
    return {
        "candidate_id": resume_record["candidate_id"],
        "name": None,
        "email": None,
        "phone": None,
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "extraction_status": "text_extracted_needs_structuring",
        "text_length": len(text),
        "note": "Wire the existing section/skill/education parsers here to populate structured fields.",
    }


def score_adapter(candidate: CandidateProfile, job: JobProfile) -> dict[str, Any]:
    """Transparent baseline scorer. Replace with the repository's verified ATS scoring engine."""
    required = {s.strip().casefold() for s in job.required_skills if s.strip()}
    candidate_skills = {s.strip().casefold() for s in candidate.skills if s.strip()}
    skill_score = 100.0 if not required else 100.0 * len(required & candidate_skills) / len(required)
    # Deliberately label the result as a baseline: do not invent experience/education/semantic scores.
    return {
        "overall_score": round(skill_score, 2),
        "score_breakdown": {"skill_match": round(skill_score, 2)},
        "scoring_method": "required_skill_overlap_baseline",
        "note": "Prototype baseline only; replace with approved ATS scoring engine and require recruiter review.",
    }


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
        logger.exception("task_id=%s operation failed", task_id)
        task["status"] = "failed"
        task["result"] = None
        task["error"] = {"code": "PROCESSING_FAILED", "message": "The task could not be completed."}
    finally:
        task["updated_at"] = now_iso()


def create_task(operation: str) -> str:
    task_id = new_id("task")
    TASKS[task_id] = {
        "task_id": task_id,
        "operation": operation,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return task_id


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
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_RESUME_FORMAT", "message": "Only PDF and DOCX files are supported."}})
    resume_id = new_id("res")
    destination = UPLOAD_DIR / f"{resume_id}{suffix}"
    size = 0
    try:
        with destination.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    out.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail={"error": {"code": "FILE_TOO_LARGE", "message": "Maximum upload size is 10 MB."}})
                out.write(chunk)
    finally:
        await file.close()

    RESUMES[resume_id] = {
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "path": str(destination),
        "filename": Path(file.filename or "resume").name,
        "size_bytes": size,
        "created_at": now_iso(),
        "parsed_profile": None,
    }
    task_id = create_task("parse_resume")
    asyncio.create_task(run_task(task_id, parse_resume_adapter, RESUMES[resume_id]))
    return {"resume_id": resume_id, "task_id": task_id, "status": "queued", "message": "Resume accepted for parsing"}


@app.post(f"{API_PREFIX}/resumes/{{resume_id}}/parse", status_code=202)
async def parse_resume(resume_id: str):
    record = RESUMES.get(resume_id)
    if not record:
        raise HTTPException(status_code=404, detail={"error": {"code": "RESUME_NOT_FOUND", "message": "The requested resume does not exist."}})
    task_id = create_task("parse_resume")
    asyncio.create_task(run_task(task_id, parse_resume_adapter, record))
    return {"resume_id": resume_id, "task_id": task_id, "status": "queued"}


@app.post(f"{API_PREFIX}/candidates/{{candidate_id}}/score", status_code=202)
async def score_candidate(candidate_id: str, payload: ScoreRequest):
    candidate = payload.candidate_profile
    if candidate is None and payload.resume_id:
        record = RESUMES.get(payload.resume_id)
        if not record:
            raise HTTPException(status_code=404, detail={"error": {"code": "RESUME_NOT_FOUND", "message": "The requested resume does not exist."}})
        parsed = record.get("parsed_profile")
        if not parsed:
            raise HTTPException(status_code=400, detail={"error": {"code": "PROFILE_NOT_READY", "message": "Provide candidate_profile or wait until parsing has completed and structured profile integration is configured."}})
        candidate = CandidateProfile(**parsed)
    if candidate is None:
        raise HTTPException(status_code=400, detail={"error": {"code": "CANDIDATE_PROFILE_REQUIRED", "message": "Provide candidate_profile or a parsed resume profile."}})
    task_id = create_task("score_candidate")
    asyncio.create_task(run_task(task_id, score_adapter, candidate, payload.job_profile))
    TASKS[task_id]["candidate_id"] = candidate_id
    TASKS[task_id]["job_id"] = payload.job_id
    return {"task_id": task_id, "candidate_id": candidate_id, "job_id": payload.job_id, "status": "queued"}


@app.post(f"{API_PREFIX}/jobs/{{job_id}}/shortlist", status_code=202)
async def shortlist(job_id: str, payload: ShortlistRequest):
    task_id = create_task("shortlist")
    asyncio.create_task(run_task(task_id, build_shortlist, job_id, payload))
    TASKS[task_id]["job_id"] = job_id
    return {"task_id": task_id, "job_id": job_id, "status": "queued"}


def build_shortlist(job_id: str, payload: ShortlistRequest) -> dict[str, Any]:
    ordered = sorted(payload.candidates, key=lambda c: c.overall_score, reverse=True)[:payload.top_n]
    rows = []
    for rank, candidate in enumerate(ordered, start=1):
        if candidate.overall_score >= payload.shortlist_threshold:
            decision = "shortlisted"
        elif candidate.overall_score >= payload.review_threshold:
            decision = "review"
        else:
            decision = "not_shortlisted"
        rows.append({
            "candidate_id": candidate.candidate_id,
            "overall_score": candidate.overall_score,
            "decision": decision,
            "rank": rank,
        })
    result = {
        "job_id": job_id,
        "status": "completed",
        "count": len(rows),
        "candidates": rows,
        "decision_policy": {
            "shortlist_threshold": payload.shortlist_threshold,
            "review_threshold": payload.review_threshold,
            "human_review_required": True,
        },
    }
    JOB_RANKINGS[job_id] = result
    return result


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/rankings")
async def get_rankings(job_id: str):
    result = JOB_RANKINGS.get(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "RANKINGS_NOT_FOUND", "message": "No ranking result exists for this job."}})
    return result


@app.get(f"{API_PREFIX}/tasks/{{task_id}}")
async def get_task(task_id: str):
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "TASK_NOT_FOUND", "message": "The requested task does not exist."}})
    response = dict(task)
    response.pop("operation", None)
    return response
