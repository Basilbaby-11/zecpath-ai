# Zecpath ATS — Developer Guide

**Day 19 deliverable | Version 1.0**

## 1. Audience and prerequisites

This guide is for developers setting up, testing, and extending the Zecpath ATS Python repository.

Recommended environment:
- Windows, macOS, or Linux
- Python 3.11 (the project has previously been exercised with Python 3.11.x; confirm compatibility when changing versions)
- Git
- VS Code or another Python IDE
- Tesseract OCR installed separately if OCR fallback is required

## 2. Repository map

```text
zecpath-ai/
├── api/                 # FastAPI application and endpoint adapters
├── ats_engine/          # Skill, semantic, experience matching
├── config/              # Scoring weights and shortlist thresholds
├── docs/                # Technical and developer documentation
├── fairness/            # Masking, normalization, bias evaluation utilities
├── interview_ai/        # Interview AI foundation
├── parsers/             # Resume, JD, skill, education and experience parsing
├── ranking/             # Candidate ranking
├── reports/             # Evaluation and performance reports
├── scoring/             # Weighted ATS score calculation
├── screening_ai/        # Screening foundation
├── scripts/             # Batch pipelines and evaluation scripts
├── shortlisting/        # Shortlisting classification
├── tests/               # Unit and integration tests
├── utils/               # Shared utilities and logging
├── config/
├── requirements.txt
├── pyproject.toml
├── resume_schema.json
└── job_description_schema.json
```

## 3. Environment setup

### Windows PowerShell

```powershell
# Move into the repository root
cd path\to\zecpath-ai

# Create a virtual environment
py -3.11 -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install repository dependencies
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the current-user execution policy permitted by your organization, or run the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS / Linux

```bash
cd path/to/zecpath-ai
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Optional semantic matching dependency

`ats_engine/semantic_matching_engine.py` imports Sentence Transformers lazily and uses `sentence-transformers/all-MiniLM-L6-v2` by default. The current `requirements.txt` does not list `sentence-transformers`, so install it when using that engine:

```bash
python -m pip install sentence-transformers
```

The model may be downloaded the first time it is used. Ensure the runtime has access to the model cache or provide an approved preloaded model strategy in restricted environments.

### Optional OCR dependency

The Python requirements include `pytesseract`, `Pillow`, and `pdf2image`, but Tesseract OCR is a separate system installation. Install Tesseract and ensure its executable is on `PATH`. Depending on the PDF conversion setup, Poppler may also be required by `pdf2image`.

## 4. Configuration

### ATS weights

Edit `config/ats_scoring_weights.json` to change default or role-specific component weights. The weights for each profile must be non-negative and sum to exactly `1.0` (within the scorer's validation tolerance).

Current defaults:
- `skill_match`: `0.35`
- `experience_relevance`: `0.25`
- `education_alignment`: `0.15`
- `semantic_similarity`: `0.25`

Current role overrides include `AI Engineer` and `Python Developer`.

### Shortlisting thresholds

`config/shortlisting_thresholds.json` currently defines:
- `shortlist_min`: `70`
- `review_min`: `60`

The module built-in defaults and API request defaults are currently `75` and `50`. Confirm which values the calling workflow passes. Do not assume the JSON file is automatically loaded by every call. Keep the configuration source consistent and cover it with tests.

### Skill dictionary

The README documents `data/skill_dictionary.json` as the default skill dictionary path for Skill NER. Batch scripts can accept a custom dictionary path. Confirm that the dictionary exists in the local working copy before running dictionary-dependent processing.

## 5. Running the API

From the repository root with the virtual environment active:

```bash
uvicorn api.main:app --reload
```

Default local address: `http://127.0.0.1:8000`

Useful URLs:
- Health: `http://127.0.0.1:8000/health`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

The API creates its upload directory using `ZECPATH_UPLOAD_DIR`, defaulting to `data/api_uploads`. `LOG_LEVEL` controls the logging level, defaulting to `INFO`.

**Prototype warning:** The API's task, resume, and ranking registries are in memory. Restarting the process loses that state. Do not use this implementation as a production service or with real candidate data without the security, persistence, and privacy work described in the technical documentation.

## 6. API endpoint summary

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/` | Service metadata |
| GET | `/health` | Health status |
| POST | `/api/v1/resumes` | Multipart upload; PDF/DOCX; max 10 MB; requires `candidate_id`, optional `job_id` |
| POST | `/api/v1/resumes/{resume_id}/parse` | Queue parsing for an uploaded resume |
| POST | `/api/v1/candidates/{candidate_id}/score` | JSON payload with `job_id`, optional `role`, and `component_scores` |
| POST | `/api/v1/jobs/{job_id}/shortlist` | JSON candidate list and optional threshold/top-N values |
| GET | `/api/v1/jobs/{job_id}/rankings` | Rankings for a job in current process |
| GET | `/api/v1/tasks/{task_id}` | Task status and result |

### Example: health check

```bash
curl http://127.0.0.1:8000/health
```

### Example: upload a resume

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/resumes" \
  -F "candidate_id=CAND001" \
  -F "job_id=JOB001" \
  -F "file=@./sample_resume.pdf"
```

The API returns HTTP `202 Accepted` with a `resume_id`, `task_id`, and queued status. Poll the task endpoint:

```bash
curl "http://127.0.0.1:8000/api/v1/tasks/TASK_ID"
```

Use the actual task ID returned by the upload response.

### Example: score supplied component outputs

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/candidates/CAND001/score" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "JOB001",
    "role": "AI Engineer",
    "component_scores": {
      "skill_match": 80,
      "experience_relevance": 65,
      "education_alignment": 75,
      "semantic_similarity": 82
    }
  }'
```

This endpoint scores supplied component values. It does not itself parse the resume or calculate all four components from raw documents.

## 7. Running batch scripts

Use `python path/to/script.py --help` where the script supports command-line arguments. Examples in the repository include:
- `scripts/combined_resume_pipeline.py`
- `scripts/experience_batch_pipeline.py`
- `scripts/run_semantic_matching_batch.py`
- `scripts/generate_ats_scores_from_semantic_results.py`
- `scripts/generate_ranked_candidates.py`
- `scripts/run_fairness_pipeline.py`
- `scripts/evaluate_day17_dataset.py`
- `scripts/benchmark_day18.py`

Check each script's arguments and input directory assumptions before execution. Generated data folders may be ignored by Git and may not be included in a clean clone or source archive.

## 8. Testing and code quality

Run the full test suite:

```bash
python -m pytest -q
```

Run a specific test file:

```bash
python -m pytest tests/test_ats_engine.py -q
python -m pytest tests/test_day16_api_integration.py -q
python -m pytest tests/test_day17_system_testing.py -q
python -m pytest tests/test_day18_optimization.py -q
```

Run Ruff if installed:

```bash
ruff check .
```

When changing code:
1. Add or update a focused unit test.
2. Add an integration test when module contracts or API behavior change.
3. Run the focused test first.
4. Run the full suite.
5. Re-run relevant evaluation/benchmark scripts.
6. Update documentation and configuration examples.

## 9. Scoring behavior developers must preserve

- Component scores use a `0–100` scale.
- Configured weights must sum to `1.0`.
- Missing component scores are excluded; remaining weights are renormalized.
- Missing values must not be converted to zero.
- No available component scores results in `overall_score: null`.
- Incomplete data should route to manual review in shortlisting.
- Ranking is scoped by job and ties share competition ranks.
- Scores are not probabilities or final hiring decisions.

## 10. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `ModuleNotFoundError` for a project package | Running from the wrong directory or wrong interpreter | Change to repository root; activate `.venv`; use `python -m ...` |
| `ModuleNotFoundError: sentence_transformers` | Optional semantic dependency is not installed | Install `sentence-transformers` in the active environment |
| Semantic model download/cache error | First run requires model access or cache is unavailable | Check network/model cache; pre-provision an approved model in offline environments |
| OCR returns no text | Tesseract missing, not on PATH, or image quality is poor | Verify `tesseract --version`; inspect OCR input and image resolution |
| `pdf2image` conversion fails | Poppler is missing or not configured | Install Poppler and configure PATH as required by the OS |
| Resume upload returns 400 | File extension is not PDF/DOCX | Use a supported file type |
| Resume upload returns 413 | File exceeds 10 MB | Use an appropriately sized document or revise the documented limit with tests |
| Task ID not found after restart | API state is in memory | Restart the request flow; durable task storage is a production requirement |
| Weight validation fails | Weights are negative or do not sum to 1.0 | Correct the JSON profile and re-run scoring tests |
| Shortlisting result differs from expected threshold | Config JSON and module/API defaults differ | Check the threshold values passed by the caller and unify the source |
| No skill entities found | Skill dictionary missing or vocabulary does not contain aliases | Verify dictionary path/content and test a known sample |
| Tests run against unexpected Python | IDE/terminal interpreter mismatch | Check `python --version` and `python -m pip --version` |

## 11. Extension guidelines

### Add a new scoring component
1. Implement a focused engine with a documented output contract.
2. Add a component key and weight to the default and relevant role profiles.
3. Ensure the profile sums to `1.0`.
4. Update score extraction/adapters if the engine returns a new result shape.
5. Add tests for valid, missing, invalid, and boundary values.
6. Update technical documentation and scoring explanation output.

### Add a new parser field
1. Add extraction logic to the appropriate parser.
2. Update `resume_schema.json` or `job_description_schema.json`.
3. Update downstream adapters and normalization.
4. Add representative tests for populated and missing values.
5. Update schema/version documentation.

### Add or change an API endpoint
1. Define and validate a Pydantic request model.
2. Return stable response and error structures.
3. Add request ID-aware logging.
4. Add endpoint integration tests.
5. Consider authentication, authorization, rate limiting, persistence, and privacy before production exposure.

## 12. Handover checklist

- [ ] Developer can create and activate the virtual environment.
- [ ] Dependencies and optional system tools are documented.
- [ ] API starts and health endpoint responds.
- [ ] Resume upload and task polling are understood.
- [ ] Scoring weights and threshold differences are reviewed.
- [ ] Full automated test suite passes in the handover environment.
- [ ] Sample input/output data is available and contains no real personal data.
- [ ] Production limitations and security gaps are understood.
- [ ] Documentation is updated alongside code changes.
