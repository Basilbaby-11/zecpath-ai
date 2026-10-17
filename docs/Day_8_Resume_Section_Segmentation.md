# Day 8 — Resume Section Segmentation

## Objective

Segment text already extracted by `parsers/resume_extractor.py` into labeled resume sections without changing the Day 5 extraction stage or the existing resume JSON schema.

## Implementation

- `parsers/heading_patterns.py`: canonical section labels and common heading aliases.
- `parsers/resume_section_classifier.py`: heading detection, normalization, lightweight content-clue classification, section segmentation, and per-block labels.
- `data/section_segmentation/labeled_samples.json`: manually labeled heading/content examples for repeatable evaluation.
- `tests/test_resume_section_classifier.py`: unit tests for heading variations, content preservation, and invalid/empty input.

The classifier uses transparent rules and keyword clues rather than a trained NLP model. Confidence values are heuristic scores and are not calibrated probabilities. Unknown text is preserved instead of discarded. A headingless preamble is assigned to a likely section or `summary` as a fallback.

## Usage

Run from the repository root:

```powershell
python -c "from parsers.resume_section_classifier import segment_file; import json; print(json.dumps(segment_file('data/extracted_resumes/sample_resume_docx.txt'), indent=2))"
pytest -q
```

The result contains `parser_version`, `source_document`, `sections`, `blocks`, `section_count`, and `unclassified_block_count`. The `sections` object includes skills, work experience, education, certifications, projects, and additional common sections.

## Accuracy evaluation

The labeled sample file is a small, curated smoke-test dataset, not a representative benchmark. Heading examples should be evaluated with `detect_heading`; content examples should be evaluated with `classify_block`. Report results separately by task and class. Do not present this small set as production accuracy. For a meaningful report, label full resumes from varied layouts, split by resume (not by individual line) into development and held-out test sets, and report per-section precision, recall, F1, plus overall block accuracy. Human review is needed for ambiguous or malformed resumes.

## Limitations

- Table rows and multi-column reading order depend on the upstream extractor's text order.
- Content clues can be ambiguous; explicit section headings are preferred.
- This module segments text; it does not yet extract structured employment dates, employer names, skill entities, or education fields.
- Sensitive candidate content should not be added to logs. Use anonymized or consented samples for evaluation.
