# Day 18 — Stability Improvements

- Semantic section inputs are batched to reduce repeated encoder/framework overhead.
- Empty resume/job sections are skipped and marked `insufficient_data`, preventing meaningless embedding calls.
- Added tests for batched inference, empty sections, noisy text normalization, and unsupported file types.
- Added an extraction benchmark with per-file error capture, median/minimum latency, word count, and Python-tracked peak memory.
- Existing extraction behavior retains OCR fallback for short PDF text and image-bearing DOCX files.

## Operational recommendations
- Keep model loading lazy and reuse a `SemanticMatchingEngine` instance for multiple requests when the hosting process lifecycle permits it.
- Bound upload size and page count at the API boundary; use worker/process limits for OCR-heavy documents.
- Record errors without logging resume contents or unnecessary personal data.
- Re-run tests and benchmarks on the deployment OS before claiming production readiness.
