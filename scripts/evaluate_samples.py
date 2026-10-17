"""Evaluate labeled heading snippets and complete resume samples.

Run from the repository root:
    python scripts/evaluate_samples.py

Complete-resume metrics are block-level and use manually annotated expected_sections.
They measure this small fixture set only; they are not a production benchmark.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from parsers.resume_section_classifier import classify_block, detect_heading, segment_resume

SNIPPETS = ROOT / "data" / "section_segmentation" / "labeled_samples.json"
RESUMES = ROOT / "data" / "section_segmentation" / "complete_resume_samples.json"
REPORT = ROOT / "reports" / "section_detection_accuracy_report.md"


def metrics(rows):
    labels = sorted({r["expected"] for r in rows} | {r["predicted"] for r in rows})
    correct = sum(r["expected"] == r["predicted"] for r in rows)
    per_label = {}
    for label in labels:
        tp = sum(r["expected"] == label and r["predicted"] == label for r in rows)
        fp = sum(r["expected"] != label and r["predicted"] == label for r in rows)
        fn = sum(r["expected"] == label and r["predicted"] != label for r in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        support = sum(r["expected"] == label for r in rows)
        per_label[label] = (precision, recall, f1, support)
    macro = tuple(sum(per_label[l][i] for l in labels) / len(labels) for i in range(3)) if labels else (0,0,0)
    return correct, len(rows), (correct / len(rows) if rows else 0), per_label, macro


def main():
    snippets = json.loads(SNIPPETS.read_text(encoding="utf-8"))
    snippet_rows = []
    for sample in snippets:
        if sample["sample_id"].startswith("heading_"):
            pred = detect_heading(sample["text"]) or "other"
        else:
            pred, _ = classify_block(sample["text"])
        snippet_rows.append({"expected": sample["expected_section"], "predicted": pred, "id": sample["sample_id"]})

    complete = json.loads(RESUMES.read_text(encoding="utf-8"))
    block_rows = []
    resume_results = []
    for sample in complete:
        result = segment_resume(sample["text"], source_document=sample["resume_id"])
        expected_lookup = {line: section for section, lines in sample["expected_sections"].items() for line in lines}
        pred_lookup = {b["text"]: b["section"] for b in result["blocks"] if b["block_type"] == "content"}
        for line, expected in expected_lookup.items():
            predicted = pred_lookup.get(line, "missing")
            row = {"expected": expected, "predicted": predicted, "id": sample["resume_id"] + ": " + line}
            block_rows.append(row)
        resume_results.append((sample["resume_id"], result, expected_lookup, pred_lookup))

    sc, sn, sa, _, _ = metrics(snippet_rows)
    bc, bn, ba, per_label, macro = metrics(block_rows)
    lines = [
        "# Day 8 — Section Detection Evaluation Report", "",
        "## Evaluation scope", "",
        "This report includes the original curated heading/content smoke tests and a separate block-level evaluation on five synthetic, manually labeled complete-resume fixtures. The fixtures cover standard headings, alternative headings, a heading-free resume, preamble/unknown text, and a non-technical resume. These are development examples, not a representative production dataset.", "",
        "## Original snippet smoke tests", "",
        "| Task | Correct | Examples | Accuracy |", "|---|---:|---:|---:|",
        f"| Heading detection | {sum(r['expected']==r['predicted'] for r in snippet_rows if r['id'].startswith('heading_'))} | {sum(r['id'].startswith('heading_') for r in snippet_rows)} | {sum(r['expected']==r['predicted'] for r in snippet_rows if r['id'].startswith('heading_')) / max(1,sum(r['id'].startswith('heading_') for r in snippet_rows)):.1%} |",
        f"| Content-clue classification | {sum(r['expected']==r['predicted'] for r in snippet_rows if r['id'].startswith('content_'))} | {sum(r['id'].startswith('content_') for r in snippet_rows)} | {sum(r['expected']==r['predicted'] for r in snippet_rows if r['id'].startswith('content_')) / max(1,sum(r['id'].startswith('content_') for r in snippet_rows)):.1%} |", "",
        "## Complete-resume block-level results", "",
        f"- Correct blocks: **{bc}/{bn}**", f"- Block-level accuracy: **{ba:.1%}**", f"- Macro precision: **{macro[0]:.3f}**", f"- Macro recall: **{macro[1]:.3f}**", f"- Macro F1-score: **{macro[2]:.3f}**", "",
        "### Per-section metrics", "", "| Section | Precision | Recall | F1-score | Support |", "|---|---:|---:|---:|---:|"
    ]
    for label, (p, r, f1, support) in per_label.items():
        lines.append(f"| `{label}` | {p:.3f} | {r:.3f} | {f1:.3f} | {support} |")
    errors = [r for r in block_rows if r["expected"] != r["predicted"]]
    lines += ["", "### Misclassified or missing blocks", ""]
    if errors:
        for row in errors:
            lines.append(f"- `{row['id']}` — expected `{row['expected']}`, predicted `{row['predicted']}`.")
    else:
        lines.append("No block-level errors in this fixture set.")
    lines += ["", "## Interpretation and limitations", "",
        "- The complete-resume metrics are calculated by comparing each manually annotated content line with the section assigned by `segment_resume`.",
        "- The classifier is heading-led: once a heading is detected, subsequent lines remain in that section until another recognized heading appears. This can mislabel trailing notes or unheaded content.",
        "- In a resume with no headings, the current implementation classifies the preamble as one combined block; it does not reliably split multiple unheaded sections. This limitation is intentionally exposed by the fixture evaluation.",
        "- The synthetic dataset is too small to establish production performance. Add diverse real-world resumes with manually reviewed block labels, and keep a held-out test set before claiming generalization.",
        "- These metrics evaluate section segmentation only; OCR/text-extraction errors should be assessed separately.", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Snippet smoke tests: {sc}/{sn} = {sa:.1%}")
    print(f"Complete-resume blocks: {bc}/{bn} = {ba:.1%}")
    print(f"Macro precision={macro[0]:.3f}, recall={macro[1]:.3f}, F1={macro[2]:.3f}")
    print(f"Report written to: {REPORT}")
    if errors:
        print("Misclassified blocks:")
        for row in errors:
            print(f" - {row['id']}: expected {row['expected']}, predicted {row['predicted']}")

if __name__ == "__main__":
    main()
