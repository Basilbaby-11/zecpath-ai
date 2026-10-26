# Day 15 — Fairness, Normalization & Bias Reduction

## Objective

Standardize resume records, create a scoring view with direct identifiers removed, normalize component scores, measure keyword/semantic disagreement, compare baseline and experimental ranking, and report descriptive score/group indicators.

## Implemented safeguards

1. Resume normalization creates a stable schema and deduplicates skill names case-insensitively.
2. Personal-attribute masking removes known direct-identifier fields and redacts common email, phone, and date-of-birth patterns from text.
3. Score normalization maps a declared source range to 0–100 and rejects invalid ranges and out-of-range values.
4. The experimental review score blends the original overall score with semantic similarity; original scores remain preserved.
5. Keyword/semantic gap diagnostics flag large differences for human review.
6. Ranking comparison reports baseline versus experimental rank changes and top-N overlap.
7. The bias evaluator validates score records, suppresses groups below a minimum size, and reports group mean and pass-rate gaps only when an approved group field is supplied.

## Pipeline execution results

The pipeline was run from the Windows project environment with:

```powershell
python scripts/run_fairness_pipeline.py --input data/combined_resume_outputs/all_resumes_combined.json --scores-input data/ats_scores/ats_scoring_results.json
```

Reported output:

- Normalized resumes: **10**
- ATS score records audited: **100**
- Valid `overall_score` records: **100**
- Missing `overall_score` records: **0**
- Invalid `overall_score` records: **0**
- Keyword/semantic pairs checked: **100**

The pipeline generated these reports:

- `data/fairness_reports/normalized_resumes.json`
- `data/fairness_reports/masked_scoring_resumes.json`
- `data/fairness_reports/bias_indicator_report.json`
- `data/fairness_reports/normalized_ats_scores.json`

## Output verification and report observations

- The normalized resume output contains **10** records.
- The masked scoring output contains **10** records.
- The masked scoring output's resume records do not contain the `personal_info` field, based on the verification command run against the generated file.
- The bias report audited **100** valid score records.
- The keyword/semantic diagnostic checked **100** paired records. The mean absolute gap was **4.8**, and **9** records exceeded the configured gap threshold of **10**.
- The ranking comparison included **100** valid records. The baseline and experimental top 10 had **100% overlap**; mean absolute rank change was **2.8**, and the largest absolute rank change was **13**.
- The report has `group_field: null` and an empty `group_statistics` collection. Therefore, **group-level fairness comparison has not been performed**.

## Automated tests

The user reports that the **Day 15-specific test suite passed** in their Windows project environment.

To rerun the relevant Day 15 tests, use the actual fairness-related test filenames in the project's `tests` folder. For example:

```powershell
python -m pytest tests/test_fairness.py -v
```

Replace the example filename with the test file(s) that actually exist in the repository.

The full repository test suite previously stopped during collection because `tests/test_resume_extractor.py` attempted to import `normalize_heading` from `parsers.resume_extractor`, where that function was missing. A separate missing `extract_resume` entry point was also identified in the uploaded extractor implementation. Therefore, the Day 15 test success should not be represented as proof that the full repository test suite passes unless the extractor issue has been fixed and the full suite rerun successfully.

## Interpretation and limitations

- A keyword/semantic score gap is a review signal, not proof of bias.
- Ranking movement is not proof that fairness improved. Validate examples against job-related criteria and, where possible, independently reviewed outcomes.
- Group score gaps are descriptive; they do not establish causation or legal compliance.
- Do not infer protected characteristics from resumes. Use only appropriately governed audit data.
- Direct-identifier masking does not guarantee removal of indirect identifiers or proxy variables. The `candidate_id`, `source_document`, and identifying details inside free text may still need review.
- The semantic-aware score is experimental and should not automatically determine hiring outcomes.
- The masking verification confirms that `personal_info` is absent from each scoring-view resume; it does not prove that all possible identifiers or proxy attributes have been removed.
