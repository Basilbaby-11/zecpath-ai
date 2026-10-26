"""Normalize resumes, create a masked scoring view, and audit ATS score results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fairness.resume_normalizer import normalize_resume_batch
from fairness.personal_attribute_masker import mask_personal_attributes
from fairness.bias_evaluator import evaluate_bias_indicators
from fairness.scoring_normalizer import normalize_ats_score_record
from fairness.keyword_dependence import evaluate_keyword_dependence, compare_keyword_and_semantic_aware_rankings


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"JSON file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def extract_score_records(payload: Any) -> list[dict[str, Any]]:
    """Accept ATS output shaped as {'results': [...]} or a list of score rows."""
    if isinstance(payload, dict):
        records = payload.get("results")
        if records is None:
            # Permit a single score record object, but don't treat resume batches as scores.
            if "overall_score" in payload:
                records = [payload]
            else:
                raise ValueError(
                    "Score input must contain a 'results' array (ATS scoring output) "
                    "or be a list of score records."
                )
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("Score input must be a JSON object containing 'results' or a list.")

    if not isinstance(records, list):
        raise ValueError("The score input's 'results' field must be a list.")
    return [row for row in records if isinstance(row, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize combined resumes, mask identifiers, and audit ATS score results."
    )
    parser.add_argument(
        "--input",
        default="data/combined_resume_outputs/all_resumes_combined.json",
        help="Combined resume JSON input (expects a list or an object with 'resumes').",
    )
    parser.add_argument(
        "--scores-input",
        default="data/ats_scores/ats_scoring_results.json",
        help="ATS scoring JSON input (expects an object with a 'results' array).",
    )
    parser.add_argument("--normalized-output", default="data/fairness_reports/normalized_resumes.json")
    parser.add_argument("--masked-output", default="data/fairness_reports/masked_scoring_resumes.json")
    parser.add_argument("--report-output", default="data/fairness_reports/bias_indicator_report.json")
    parser.add_argument("--scoring-output", default="data/fairness_reports/normalized_ats_scores.json")
    parser.add_argument("--semantic-weight", type=float, default=0.20, help="Weight for semantic similarity in the experimental review score (0..1).")
    parser.add_argument("--group-field", default=None, help="Optional approved audit-group field already present in score records; do not infer protected traits.")
    parser.add_argument("--minimum-group-size", type=int, default=5)
    parser.add_argument(
        "--score-field",
        default="overall_score",
        help="Numeric score field to audit; missing scores are reported, never invented.",
    )
    args = parser.parse_args()

    try:
        resume_payload = load_json(Path(args.input))
        score_payload = load_json(Path(args.scores_input))
        normalized = normalize_resume_batch(resume_payload)
        masked = {
            "pipeline": "fairness_masked_scoring_view",
            "total": normalized["total"],
            "resumes": [mask_personal_attributes(row) for row in normalized["resumes"]],
        }
        score_records = extract_score_records(score_payload)
        if not 0 <= args.semantic_weight <= 1:
            raise ValueError("--semantic-weight must be between 0 and 1.")
        if args.minimum_group_size < 2:
            raise ValueError("--minimum-group-size must be at least 2 to avoid reporting singleton groups.")
        normalized_scores = [normalize_ats_score_record(row, semantic_weight=args.semantic_weight) for row in score_records]
        report = evaluate_bias_indicators(score_records, group_field=args.group_field, score_field=args.score_field, minimum_group_size=args.minimum_group_size)
        report["keyword_dependence_diagnostic"] = evaluate_keyword_dependence(score_records)
        report["ranking_comparison"] = compare_keyword_and_semantic_aware_rankings(
            score_records, semantic_weight=args.semantic_weight
        )
        report["semantic_aware_review_score"] = {
            "enabled": True, "semantic_weight": args.semantic_weight,
            "formula": "(1 - semantic_weight) * overall_score + semantic_weight * semantic_similarity",
            "note": "Experimental review aid, not a validated hiring decision. Original ATS scores are preserved.",
        }
        report["input_source"] = str(args.scores_input)
        report["note"] = (
            "Resume normalization and masking use the combined resume input. Score statistics "
            "use the ATS scoring results array, where each record represents a candidate-job pair. "
            "These descriptive statistics do not establish fairness or legal compliance. "
            "No protected traits are inferred."
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    for target_arg, data in (
        (args.normalized_output, normalized),
        (args.masked_output, masked),
        (args.report_output, report),
        (args.scoring_output, {"pipeline": "day15_scoring_normalization", "total": len(normalized_scores), "records": normalized_scores}),
    ):
        target = Path(target_arg)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote: {target}")

    print(f"Normalized resumes: {normalized['total']}")
    print(f"ATS score records audited: {report['total_records']}")
    print(f"Valid {args.score_field}: {report['valid_score_count']}")
    print(f"Missing {args.score_field}: {report['missing_score_count']}")
    print(f"Invalid {args.score_field}: {report['invalid_score_count']}")
    print(f"Keyword/semantic pairs checked: {report['keyword_dependence_diagnostic']['paired_valid_records']}")
    print("Note: masked output is a scoring view; retain identity mappings separately with access controls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
