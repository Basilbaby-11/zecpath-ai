# Day 17 — ATS Improvement Backlog

Priorities: P0 = correctness / hiring-risk blocker; P1 = important before pilot; P2 = follow-up improvement.

| ID | Priority | Item | Why it matters | Acceptance criteria |
|---|---|---|---|---|
| ATS-17-01 | P0 | Build a reviewer-labelled evaluation dataset | Synthetic tests cannot estimate real precision/recall | At least 100 anonymized resume/job pairs labelled by two reviewers, disagreements adjudicated, split documented |
| ATS-17-02 | P0 | Measure false positives and false negatives by role and experience band | Overall accuracy can hide harmful errors | Report precision, recall, F1, confusion matrix, sample counts, and confidence caveats for each sufficiently sized slice |
| ATS-17-03 | P0 | Keep human review in final hiring decisions | A score is not a validated hiring decision | API/report explicitly states decision support only; missing or borderline cases route to manual review |
| ATS-17-04 | P1 | Add role-specific weights for validated non-technical roles | Current config has explicit overrides only for AI Engineer and Python Developer | Recruiter-approved weights for each supported role, with regression tests and versioned config |
| ATS-17-05 | P1 | Test resume parsing end-to-end with anonymized PDF/DOCX/TXT fixtures | Component score tests do not prove extraction quality | Track field-level extraction precision/recall and parser failures for each supported file type |
| ATS-17-06 | P1 | Add score explanations and data-coverage warnings to recruiter output | Partial data can make scores misleading | Every score exposes component contributions, missing fields, and data-quality status |
| ATS-17-07 | P1 | Test API failure, size-limit, malformed-file, and concurrency cases | Current integration coverage is limited | Automated API tests cover validation/error paths and concurrent task handling |
| ATS-17-08 | P1 | Add persistent task/ranking storage and authentication before deployment | Current API state is in memory and development-oriented | Restart-safe persistence, authenticated access, authorization tests, and documented retention policy |
| ATS-17-09 | P2 | Monitor ranking stability and threshold sensitivity | Small score changes can alter shortlist membership | Report top-N overlap and decision changes across reasonable threshold/weight perturbations |
| ATS-17-10 | P2 | Schedule periodic bias and drift reviews | Data and role requirements change over time | Versioned quarterly evaluation, documented limitations, corrective actions, and reviewer sign-off |
| ATS-17-11 | P1 | Repair full-suite test collection error | `tests/test_resume_extractor.py` imports `normalize_heading` and `extract_resume` from the extractor module | **Completed in this update:** full suite passes 96/96 tests in Linux/Python 3.13.5; re-run on target Windows environment |

## Recommended next actions
1. **Completed:** focused Day 17/Day 16 tests pass 16/16; full suite passes 96/96 in the available Linux environment.
2. Use `data/day17_evaluation/manual_review_dataset_template.csv` to collect actual anonymized resume/job pairs with independent reviewer labels.
3. Run `scripts/evaluate_day17_dataset.py` on the completed CSV to compute precision/recall/F1 and a confusion matrix.
4. Keep ATS-17-01 through ATS-17-03 open before any live hiring pilot; synthetic metrics are not production validation.
