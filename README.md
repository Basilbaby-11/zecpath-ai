# Zecpath AI

A modular Python project for resume parsing, job-description analysis, skill extraction, experience analysis, and explainable candidate-to-job relevance scoring for the Zecpath AI-powered hiring platform.

> **Project status:** Core parsing and scoring modules are implemented with automated tests. This repository is an AI development foundation, not a complete production hiring platform. Scores are decision-support signals and should not be used as the sole basis for hiring decisions.

## Features

### Resume processing
- Extract text from PDF and DOCX resumes.
- Normalize whitespace, bullets, and common section headings.
- Use OCR as a fallback for scanned PDFs and DOCX files containing embedded images (requires Tesseract OCR).
- Produce structured JSON and cleaned text output.
- Extract basic candidate details such as name, email, phone, and skills through the batch skill-extraction pipeline.

### Resume section segmentation
- Detect common resume headings and map them to canonical sections.
- Organize resume text into sections and labeled blocks.
- Include heuristic confidence values and retain content that cannot be confidently classified.

### Skill entity recognition (Skill NER)
- Use spaCy PhraseMatcher and a canonical skill dictionary to detect skills and aliases.
- Normalize skill variations and avoid duplicate entities.
- Support batch processing of TXT, PDF, and DOCX resumes.
- The skill dictionary is expected at `data/skill_dictionary.json` unless a custom path is supplied.

### Job description parsing
- Parse job descriptions into structured fields, including role/title and skill-related information.
- Normalize known role aliases and skill variations.
- Generate a stable job identifier for parsed job descriptions.
- Validate or adapt output against the repository's job-description schema where applicable.

### Experience parsing and relevance
- Parse multiple employment experiences from resume text, including role, employer, dates, duration, and related details where available.
- Normalize common date formats and recognize current roles.
- Compare experience against a job profile using explainable skill overlap and text similarity.
- Compare role-to-role similarity using role-title and skill similarity.
- Return supporting details such as matched, missing, and additional skills. Scores are ranking aids, not calibrated probabilities.

### ATS and screening foundations
- Provide baseline ATS matching and candidate screening functions.
- Keep parsing, matching, and scoring responsibilities separated into modules for easier testing and extension.

## Repository structure

```text
zecpath-ai/
├── ats_engine/
│   ├── experience_relevance_engine.py  # Experience relevance and role similarity
│   └── matcher.py                      # ATS matching logic
├── docs/                               # Parser and segmentation documentation
├── interview_ai/                       # Interview AI module foundation
├── parsers/
│   ├── experience_parser.py             # Work experience extraction
│   ├── jd_parser.py                     # Job description parsing
│   ├── resume_extractor.py              # PDF/DOCX extraction and OCR fallback
│   ├── resume_section_classifier.py     # Resume section segmentation
│   └── skill_ner.py                     # Skill entity recognition
├── reports/                            # Evaluation reports
├── screening_ai/                       # Candidate screening foundation
├── scoring/                            # Scoring module foundation
├── scripts/
│   ├── evaluate_samples.py              # Sample evaluation script
│   └── experience_batch_pipeline.py     # Batch experience/relevance pipeline
├── tests/                              # Automated tests
├── utils/
│   └── logger.py                        # Shared logging utilities
├── .env.example
├── job_description_schema.json
├── resume_schema.json
├── main.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

Generated `data/` and `logs/` directories may be created locally when running modules. Sample inputs and the skill dictionary may need to be supplied separately if they are not present in your checkout.

## Requirements

- Python 3.11 recommended
- Git
- Dependencies in `requirements.txt`
- Tesseract OCR for OCR-based extraction
- A compatible spaCy English model (`en_core_web_sm`) is optional for the experience parser's NLP entity support; structural parsing still provides the main extraction logic
- `data/skill_dictionary.json` for the default Skill NER run

## Setup on Windows PowerShell

### 1. Clone the repository

```powershell
git clone https://github.com/Basilbaby-11/zecpath-ai.git
cd zecpath-ai
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you are using an existing project virtual environment, activate it before running commands.

### 4. Install Tesseract OCR (for scanned documents)

Install Tesseract using its [official installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html), then verify it:

```powershell
tesseract --version
```

If the executable is installed but is not on `PATH`, configure its location in the extraction code or add it to your Windows `PATH`.

### 5. Optional: install the spaCy English model

```powershell
python -m spacy download en_core_web_sm
```

## Running the modules

Run commands from the repository root (`zecpath-ai`) with the virtual environment activated.

### Resume text extraction

Place PDF/DOCX files in `data/sample_resumes/`, then run:

```powershell
python -m parsers.resume_extractor
```

The extractor writes cleaned text and structured JSON files under `data/extracted_resumes/` and logs extraction events under `logs/`.

### Job description parser

See the parser's available options:

```powershell
python -m parsers.jd_parser --help
```

Example invocation for a job description text file:

```powershell
python -m parsers.jd_parser --help
```

Use the supported CLI options shown by `--help` for your checkout and pass the appropriate input file or directory. Each parsed job description can have its own identifier.

### Skill extraction / Skill NER

The batch command processes resumes from a directory and writes a combined JSON output:

```powershell
python -m parsers.skill_ner data/sample_resumes/
```

By default, the batch output is written to `data/extracted_resumes/batch_resume_extraction.json`. Use `--help` to view available options, including a custom output path:

```powershell
python -m parsers.skill_ner --help
```

Make sure the default skill dictionary exists at `data/skill_dictionary.json`, or provide a custom dictionary path if supported by the command options.

### Resume section segmentation

The section classifier can be used from Python by importing `segment_resume` or `segment_file` from `parsers.resume_section_classifier`. See `docs/` for the design and evaluation notes.

### Experience parsing and batch relevance pipeline

Place resume files (`.pdf`, `.docx`, or `.txt`) in `data/sample_resumes_with_Experience/`, then run:

```powershell
python scripts/experience_batch_pipeline.py --input-dir data/sample_resumes_with_Experience
```

The pipeline writes its results under `data/experience_outputs/`. It includes parsed experience data, job-relevance analysis against the example job profiles, and role-to-role similarity comparisons. To score against a specific job description, check the script's `--help` options:

```powershell
python scripts/experience_batch_pipeline.py --help
```

### Main application

```powershell
python main.py
```

The main entry point may expose only the current foundation modules; it does not imply that all platform workflows are fully integrated.

## Testing

Run the complete automated test suite from the repository root:

```powershell
python -m pytest tests/ -v
```

Run an individual module's tests when debugging:

```powershell
python -m pytest tests/test_resume_extractor.py -v
python -m pytest tests/test_jd_parser.py -v
python -m pytest tests/test_skill_ner.py -v
python -m pytest tests/test_resume_section_classifier.py -v
python -m pytest tests/test_experience_parser.py -v
python -m pytest tests/test_experience_relevance.py -v
python -m pytest tests/test_experience_batch_pipeline.py -v
```

Optional lint check:

```powershell
python -m ruff check .
```

Always rerun tests after changes and report the actual result from your current environment rather than relying on a previously recorded test count.

## Configuration and outputs

- `resume_schema.json`: expected resume data structure.
- `job_description_schema.json`: expected job-description data structure.
- `.env.example`: example environment configuration; copy it to `.env` only if the project needs local environment variables.
- `data/`: local input files, dictionaries, and generated results.
- `logs/`: local extraction/application logs.
- `reports/`: evaluation summaries.

Do not commit secrets, access tokens, private candidate resumes, or generated personal data to the repository. Review `.gitignore` before adding files.

## Development principles

- Keep modules small and separated by responsibility.
- Use clear names, type hints, and documented public functions.
- Add tests for new behavior and edge cases.
- Validate inputs and structured outputs.
- Keep scoring explainable and inspectable.
- Protect candidate data and credentials.
- Treat automated scores as decision-support signals; human review remains necessary.

## Current implementation summary

Implemented modules in this repository include resume text extraction, OCR fallback, resume section segmentation, job-description parsing, dictionary-guided skill entity recognition, experience parsing, experience relevance scoring, role-to-role similarity, baseline ATS matching, and candidate-screening foundations. Automated tests are provided under `tests/`; their current pass count depends on installed dependencies and required local data fixtures.

Some platform areas, including interview intelligence, behavior analysis, and end-to-end hiring orchestration, remain foundations or future integration work rather than a complete production implementation.
