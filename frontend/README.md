# Zecpath ATS React Frontend

A recruiter-facing React/Vite dashboard for the existing Zecpath FastAPI prototype.

## Features

- Recruiter dashboard with candidate/job overview
- Candidate table and search
- Upload PDF/DOCX resume using `POST /api/v1/resumes`
- Poll asynchronous task status using `GET /api/v1/tasks/{task_id}`
- Create a job from pasted text or upload a TXT/PDF/DOCX job description
- Automatically score each uploaded resume against its selected saved job description
- Recalculate a candidate score using `POST /api/v1/candidates/{candidate_id}/score`
- Generate ranking/shortlist using `POST /api/v1/jobs/{job_id}/shortlist`
- Read ranking results from `GET /api/v1/jobs/{job_id}/rankings`
- Evaluation caveats panel

## Automatic ATS scoring workflow

1. Open **Jobs** and add a job description by pasting its text or uploading TXT, PDF or DOCX.
2. Open **Upload resume**, choose the saved job and upload a PDF or DOCX resume.
3. The API extracts the full resume text, runs the existing skill, experience and education parsers, calculates matching components, and calls the existing weighted ATS scoring engine. The semantic component uses the existing Sentence Transformers engine when its dependency/model is available; if unavailable, that component is reported as missing and the weighted engine renormalizes the available component weights.
4. The generated score and evidence are returned in the task result and candidate list. The score is a decision-support signal, not a hiring probability or an automatic hiring decision.

The prototype still stores jobs, resumes, tasks and scores in memory. They are lost when the API process restarts. Add a database, authentication, authorization, privacy controls and production deployment hardening before using real applicant data.

## 1. Install frontend dependencies

Open PowerShell in this folder:

```powershell
npm install
```

## 2. Configure API URL

Copy `.env.example` to `.env` (or create `.env`) and set:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 3. Enable CORS in FastAPI

The current `api/main.py` does not show CORS middleware. Since Vite runs on port 5173 and FastAPI on port 8000, add the following near the imports and before route definitions in `api/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, replace the development origins with the exact deployed frontend origin. Do not use wildcard origins with credentials.

## 4. Start the backend

In a separate terminal at the Zecpath repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload
```

Check `http://127.0.0.1:8000/health`.

## 5. Start the frontend

In this frontend folder:

```powershell
npm run dev
```

Open `http://localhost:5173`.

## 6. Build for deployment

```powershell
npm run build
```

The production build is created in `dist/`.

## Demo flow

1. Check that the API status indicator says **API connected**.
2. Upload a PDF or DOCX resume.
3. Wait for parsing to complete. The profile's extracted skills are shown in the candidate table.
4. Select **Score candidate** and enter component scores. The existing API requires these inputs.
5. Select **Rank & shortlist** to submit scored candidates for the selected job.
6. Review the returned rankings and status.

## API contract used

- `GET /health`
- `GET /api/v1/candidates` (parsed candidate records held by the running API process)
- `POST /api/v1/resumes` (`multipart/form-data`: `file`, `candidate_id`, optional `job_id`)
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/candidates/{candidate_id}/score`
- `POST /api/v1/jobs/{job_id}/shortlist`
- `GET /api/v1/jobs/{job_id}/rankings`
