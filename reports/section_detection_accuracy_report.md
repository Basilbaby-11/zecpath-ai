# Day 8 — Section Detection Accuracy Report

## Evaluation result

This is a **curated smoke-test evaluation**, not a production benchmark.

| Evaluation task | Correct | Labeled examples | Accuracy |
|---|---:|---:|---:|
| Heading detection | 16 | 16 | 100.0% |
| Content-clue classification | 4 | 4 | 100.0% |


## Interpretation

- Heading detection achieved 16/16 on the curated heading-variation examples.
- Content-clue classification achieved 4/4 on the curated content examples after rule refinement.
- These examples were manually selected to test known behavior. The scores must not be interpreted as expected real-world resume accuracy.
- The automated repository test suite passed **30 tests** in the implementation environment.

## Recommended next evaluation

1. Label complete resumes from different industries and layouts, including tables and two-column documents.
2. Have a second reviewer validate section labels for ambiguous blocks.
3. Split the dataset by resume into development and held-out test sets.
4. Report per-section precision, recall, F1-score, confusion matrix, and block-level accuracy on the held-out set.
5. Track OCR/extraction errors separately from section-classification errors.

## Output samples

Segmented JSON smoke-test outputs for the extracted text samples are in `data/section_segmentation/predictions/`. Inspect these before using the output in downstream ATS processing.
