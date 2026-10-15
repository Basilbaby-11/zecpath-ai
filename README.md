# Zecpath AI System

## Overview

Zecpath AI is a modular AI development project supporting an AI-powered hiring platform. The repository provides a foundation for resume analysis, candidate screening, interview intelligence, evidence analysis, and scoring workflows.

## AI Modules

- **ATS Engine:** Resume processing, skill extraction integration, and job-requirement matching.
- **Screening AI:** Candidate profile validation and initial screening workflows.
- **Interview AI:** Interview transcript processing and interview intelligence.
- **Behavior Analysis:** Analysis of relevant session events and supporting evidence.
- **Scoring:** Aggregation of validated assessment results and decision-support outputs.
- **Parsers:** Resume and document parsing, text extraction, normalization, and OCR fallback for image-based resumes.
- **Utils:** Shared logging, configuration, and helper functions.

## Project Structure

```text
zecpath-ai/
├── data/
│   ├── sample_resumes/       # Sample PDF and DOCX resumes
│   └── extracted_resumes/    # Extracted TXT and JSON outputs
├── parsers/                  # Resume and document parsers
│   └── resume_extractor.py   # PDF/DOCX extraction and OCR fallback
├── ats_engine/               # ATS matching logic
├── screening_ai/             # Screening workflows
├── interview_ai/              # Interview intelligence
├── behavior_analysis/        # Behavior and evidence analysis
├── scoring/                  # Score aggregation
├── utils/                    # Shared utilities and logging
├── tests/                    # Automated tests
├── logs/                     # Local application and test logs
├── main.py                   # Application entry point
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Tool configuration
├── .env.example              # Environment variable template
├── .gitignore
└── README.md
```

## Environment Setup

Requirements:

- Python 3.11
- Git
- Tesseract OCR for image-based resume extraction

### 1. Clone the repository

```powershell
git clone <YOUR_REPOSITORY_URL>
cd zecpath-ai
```

Replace `<YOUR_REPOSITORY_URL>` with your actual Git repository URL.

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Install Tesseract OCR

Tesseract is a separate Windows application; installing the Python package `pytesseract` alone is not sufficient.

Install Tesseract using the [official installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html).

Verify the installation:

```powershell
tesseract --version
```

If Tesseract is installed but not available on PATH, configure its executable path in the Python application.

## Resume Text Extraction

The resume extraction engine supports:

- PDF and DOCX documents.
- Text extraction from digitally readable resumes.
- Text cleaning, whitespace normalization, and bullet normalization.
- Standardization of recognized section headings.
- Tested table and two-column resume layouts.
- OCR fallback for scanned PDFs and DOCX files containing embedded resume images.
- Structured TXT and JSON output files.
- Extraction logging and automated tests.

### Run the extractor

```powershell
python .\parsers\resume_extractor.py
```

### Output locations

- `data/extracted_resumes/`: cleaned TXT files and structured JSON results.
- `logs/extraction.log`: extraction successes and failures.
- `logs/test_results.txt`: saved automated test report.

### OCR limitations

OCR accuracy depends on image quality, font size, orientation, and document layout. Extracted text should be checked for recognition errors. Complex layouts may require additional handling.

## Run the Application

```powershell
python main.py
```

## Run Tests

Run the complete test suite:

```powershell
python -m pytest tests/ -v
```

To save a test report:

```powershell
python -m pytest tests/ -v > logs/test_results.txt 2>&1
```

The current resume extraction test suite has **10 passing tests**, according to the latest reported run. Run the tests again after code changes to verify the current result.

## Code Quality

Run Ruff if it is installed in your environment:

```powershell
python -m ruff check .
```

## Logging

The resume extraction engine writes extraction events to `logs/extraction.log`. Other application modules may use the shared logging utility and `logs/zecpath_ai.log`.

Avoid logging sensitive candidate information, credentials, or unnecessary personal data.

## Development Standards

- Follow PEP 8 conventions and use clear, descriptive names.
- Use type hints for public functions.
- Keep AI modules separated by responsibility.
- Write automated tests for new functionality.
- Document public functions and important design decisions.
- Store credentials in environment variables, never in source code.
- Validate inputs and outputs at service boundaries.
- Treat AI scores as decision-support signals, not as the sole basis for hiring decisions.
- Verify extracted resume content before using it in downstream screening workflows.

## Current Status

The repository structure and initial module foundations have been established.

### Completed

- Python 3.11 virtual environment setup.
- Modular project directory structure.
- Shared logging system.
- Sample ATS skill-matching functionality.
- Candidate profile validation function.
- PDF and DOCX resume text extraction.
- Text cleaning, heading normalization, and bullet normalization.
- Tested two-column PDF and DOCX resume samples.
- OCR fallback for image-only PDF and image-based DOCX samples.
- Structured TXT and JSON extraction outputs.
- Automated resume extraction tests: 10 passed in the latest reported run.
