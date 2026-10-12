# Zecpath AI System

## Overview

Zecpath AI is a modular AI development project supporting an AI-powered hiring platform. The repository provides a foundation for resume analysis, candidate screening, interview intelligence, evidence analysis, and scoring workflows.

## AI Modules

- **ATS Engine:** Resume processing, skill extraction integration, and job-requirement matching.
- **Screening AI:** Candidate profile validation and initial screening workflows.
- **Interview AI:** Interview transcript processing and interview intelligence.
- **Behavior Analysis:** Analysis of relevant session events and supporting evidence.
- **Scoring:** Aggregation of validated assessment results and decision-support outputs.
- **Parsers:** Resume and document parsing components.
- **Utils:** Shared logging, configuration, and helper functions.

## Project Structure

```text
zecpath-ai/
├── data/                 # Local test data
├── parsers/              # Resume and document parsers
├── ats_engine/           # ATS matching logic
├── screening_ai/         # Screening workflows
├── interview_ai/         # Interview intelligence
├── scoring/              # Score aggregation
├── utils/                # Shared utilities and logging
├── tests/                # Automated tests
├── logs/                 # Local application logs
├── main.py               # Application entry point
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Tool configuration
├── .env.example          # Environment variable template
├── .gitignore
└── README.md
```

## Environment Setup

Requirements: Python 3.11 and Git.

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the Application

```powershell
python main.py
```

## Run Tests

```powershell
python -m pytest -v
```

## Code Quality

```powershell
python -m ruff check .
```

## Logging

The shared logging utility writes application logs to the console and `logs/zecpath_ai.log`. Sensitive candidate information and credentials must not be written to logs.

## Development Standards

- Follow PEP 8 conventions and use clear, descriptive names.
- Use type hints for public functions.
- Keep AI modules separated by responsibility.
- Write automated tests for new functionality.
- Document public functions and important design decisions.
- Store credentials in environment variables, never in source code.
- Validate inputs and outputs at service boundaries.
- Treat AI scores as decision-support signals, not as the sole basis for hiring decisions.

## Current Status

Initial repository structure, logging, sample module functions, and automated tests are being established.

Completed:

- Python 3.11 virtual environment setup.
- Modular project directory structure.
- Shared logging system with console and file output.
- Sample ATS skill-matching functionality.
- Candidate profile validation function.
- Automated tests using pytest (4 tests passed).
- Code quality verification using Ruff (all checks passed).
- Git repository initialized and project pushed to GitHub.