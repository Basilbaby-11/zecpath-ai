# Day 18 — ATS Performance Report

## Scope
This update batches semantic resume/job section embeddings into a single encoder call rather than making a separate encoder call for each populated section. Empty sections are excluded from embedding and remain marked `insufficient_data`. A local extraction benchmark script records latency and Python-tracked peak allocations for bundled PDF/DOCX samples.

## How to measure
Run from the repository root:

```powershell
python scripts/benchmark_day18.py --iterations 3 --output reports/DAY18_BENCHMARK_RESULTS.json
```

Run functional and regression tests:

```powershell
python -m pytest tests/test_day18_optimization.py tests/test_day17_system_testing.py tests/test_day16_api_integration.py -v
```

## Results
Populate measured results from `DAY18_BENCHMARK_RESULTS.json` after running on the target machine. Do not claim a speedup until the same inputs have been benchmarked against the previous revision under the same environment. The semantic optimization's functional test asserts that one encoder call is used for all four populated sections.

## Limitations
- The included sample corpus is small and does not represent all production resumes.
- `tracemalloc` captures Python-tracked allocations, not total process memory or native library allocations.
- OCR latency can vary significantly with scanned PDFs, page count, image resolution, and local Tesseract configuration.
- Similarity scores remain ranking signals, not calibrated hiring probabilities.
