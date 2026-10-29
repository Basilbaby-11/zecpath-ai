# Day 17 — ATS System Testing Report

## Objective
Validate the current Zecpath ATS scoring, ranking, and shortlisting foundation for role adaptability, predictable behavior, and data-quality handling.

## Scope
- Role profiles: AI Engineer, Python Developer, HR Executive, Operations Manager.
- Scenario categories: technical roles, non-technical roles, fresher-style profiles, senior-style profiles, role mismatch, borderline scores, and incomplete component data.
- Components exercised: configured weighted scoring (`scoring/ats_scoring_engine.py`), ranking (`ranking/candidate_ranking_engine.py`), shortlisting classification (`shortlisting/shortlisting_engine.py`), and Day 16 API integration tests.
- Validation includes expected decisions in a small deterministic, hand-labelled test fixture. These are synthetic component-score scenarios, not real candidate resumes or a statistically representative hiring dataset.

## Test approach
1. Score each scenario using the repository's configured weights and role-specific overrides.
2. Classify scores with a test threshold of shortlist >= 70, review >= 50 and < 70, reject < 50. Missing scores must remain in manual review.
3. Verify ranking is descending and missing scores are placed last without a numeric rank.
4. Verify invalid score values and invalid thresholds are rejected.
5. Run the existing API integration tests as regression coverage.

## Test cases
| Case | Profile / condition | Expected outcome | Purpose |
|---|---|---|---|
| T01 | Technical fresher — AI Engineer | Shortlisted | Check role weighting with strong skills/education and lower experience |
| T02 | Technical senior — Python Developer | Shortlisted | Check stronger experience relevance |
| T03 | Technical role mismatch — AI Engineer | Rejected | Low skills and semantic relevance should not rank highly |
| T04 | Non-technical fresher — HR Executive | Shortlisted | Check unknown-role fallback weights and fresher-style scores |
| T05 | Non-technical senior — Operations Manager | Shortlisted | Check unknown-role fallback with strong experience |
| T06 | Role mismatch — Python Developer | Rejected | Check low job relevance |
| T07 | Borderline — AI Engineer | Review | Ensure middle-band score is not auto-shortlisted |
| T08 | Incomplete component data | Review | Check missing components are tracked and available weights renormalized |
| T09 | Ranking order / missing score | Pass expected ordering | Highest score first; missing score last with rank=None |
| T10–T12 | Invalid component scores (-1, 101, boolean) | ValueError | Input validation |
| T13 | Invalid threshold order | ValueError | Threshold validation |

## Manual-review comparison and limitations
The expected labels above are manually assigned to synthetic scenarios to exercise control flow. They do **not** establish real-world precision/recall for resume-to-job matching. For a defensible production evaluation, reviewers must independently label a representative, anonymized set of actual resume/job pairs, record adjudicated shortlist/review/reject labels, and compare those labels with the ATS output. Avoid using protected attributes as scoring features; keep a human reviewer responsible for hiring decisions.

## Execution results

Executed in the available Linux / Python 3.13.5 / pytest 9.0.2 environment:

- Focused command: `python -m pytest tests/test_day17_system_testing.py tests/test_day16_api_integration.py -v`
- Day 17 tests: **13 passed, 0 failed**.
- Day 16 regression tests: **3 passed, 0 failed**.
- Combined focused run: **16 passed, 0 failed**.
- Full-suite command: `python -m pytest -q`
- Full suite: **96 passed, 0 failed**, with no collection errors.
- Synthetic scenario mismatches: **0 across the 8 Day 17 scenarios**.

The earlier `normalize_heading` collection blocker is resolved. `parsers.resume_extractor` now exports `normalize_heading` and `extract_resume`, and sample PDF/DOCX/OCR fixtures are included so extractor tests can run. Additional missing repository test resources and schema/output mismatches uncovered by the full suite were also repaired.

A separate synthetic pair evaluation is in `data/day17_evaluation/synthetic_labelled_resume_job_pairs.csv`, with calculated results in `reports/DAY17_SYNTHETIC_EVALUATION_METRICS.json`. These metrics are only a demonstration of the evaluation pipeline and are **not production accuracy**. The blank `manual_review_dataset_template.csv` is provided for actual anonymized resume/job pairs and independent reviewer labels.

Re-run both commands in the target Windows virtual environment before submission if Windows/Python 3.11 is the required target environment.

## Key observations
- The scorer supports role-specific weights for AI Engineer and Python Developer; other roles use the configured default profile unless additional role overrides are added.
- Missing component scores are excluded and remaining weights are renormalized. Day 17 testing identified that this could previously allow an incomplete profile to be auto-shortlisted; the shortlisting engine was updated to route partial/insufficient scoring inputs to manual review.
- Ranking retains records with missing scores at the bottom and assigns `rank=None`.
- Score thresholds are policy settings, not validated hiring cutoffs. They should be calibrated with recruiter-reviewed examples and monitored for false positives/false negatives.
- The current API prototype stores tasks and rankings in memory; this test suite does not validate production persistence, authentication, concurrency, or deployment reliability.

## Conclusion
This test suite checks deterministic scoring/ranking/shortlisting behavior and selected validation paths. It is a functional regression check, not evidence that the ATS is accurate on real-world candidate data. Use a labelled evaluation dataset and reviewer adjudication before claiming production accuracy.
