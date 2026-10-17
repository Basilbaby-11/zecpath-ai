# Day 8 — Section Detection Evaluation Report

## Evaluation scope

This report includes the original curated heading/content smoke tests and a separate block-level evaluation on five synthetic, manually labeled complete-resume fixtures. The fixtures cover standard headings, alternative headings, a heading-free resume, preamble/unknown text, and a non-technical resume. These are development examples, not a representative production dataset.

## Original snippet smoke tests

| Task | Correct | Examples | Accuracy |
|---|---:|---:|---:|
| Heading detection | 16 | 16 | 100.0% |
| Content-clue classification | 4 | 4 | 100.0% |

## Complete-resume block-level results

- Correct blocks: **23/29**
- Block-level accuracy: **79.3%**
- Macro precision: **0.765**
- Macro recall: **0.813**
- Macro F1-score: **0.774**

### Per-section metrics

| Section | Precision | Recall | F1-score | Support |
|---|---:|---:|---:|---:|
| `achievements` | 0.500 | 1.000 | 0.667 | 1 |
| `certifications` | 1.000 | 1.000 | 1.000 | 1 |
| `education` | 0.714 | 1.000 | 0.833 | 5 |
| `languages` | 1.000 | 1.000 | 1.000 | 1 |
| `other` | 0.000 | 0.000 | 0.000 | 2 |
| `projects` | 1.000 | 0.667 | 0.800 | 3 |
| `skills` | 0.600 | 0.750 | 0.667 | 4 |
| `summary` | 0.833 | 0.714 | 0.769 | 7 |
| `volunteer_experience` | 1.000 | 1.000 | 1.000 | 1 |
| `work_experience` | 1.000 | 1.000 | 1.000 | 4 |

### Misclassified or missing blocks

- `resume_001_standard_ai_fresher: Aarav Menon` — expected `summary`, predicted `skills`.
- `resume_001_standard_ai_fresher: AI and Data Science graduate seeking an entry-level machine learning role.` — expected `summary`, predicted `skills`.
- `resume_003_missing_headings: Python, SQL, scikit-learn` — expected `skills`, predicted `education`.
- `resume_003_missing_headings: Built a customer churn prediction project using Python` — expected `projects`, predicted `education`.
- `resume_005_nontechnical: Anjali Thomas` — expected `other`, predicted `summary`.
- `resume_005_nontechnical: ADDITIONAL NOTE: References can be provided on request.` — expected `other`, predicted `achievements`.

## Interpretation and limitations

- The complete-resume metrics are calculated by comparing each manually annotated content line with the section assigned by `segment_resume`.
- The classifier is heading-led: once a heading is detected, subsequent lines remain in that section until another recognized heading appears. This can mislabel trailing notes or unheaded content.
- In a resume with no headings, the current implementation classifies the preamble as one combined block; it does not reliably split multiple unheaded sections. This limitation is intentionally exposed by the fixture evaluation.
- The synthetic dataset is too small to establish production performance. Add diverse real-world resumes with manually reviewed block labels, and keep a held-out test set before claiming generalization.
- These metrics evaluate section segmentation only; OCR/text-extraction errors should be assessed separately.
