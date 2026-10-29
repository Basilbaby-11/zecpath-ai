"""Evaluate ATS shortlist decisions against adjudicated suitability labels.

Input CSV must contain human_review_label and ats_status. For this binary report,
shortlisted is a positive prediction; review/rejected are treated as not shortlisted.
Use only after labels are independently reviewed. Synthetic metrics are not production accuracy.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path


def calculate(rows):
    tp = fp = tn = fn = 0
    excluded = 0
    for row in rows:
        label = (row.get('human_review_label') or row.get('adjudicated_label') or '').strip().lower()
        status = (row.get('ats_status') or '').strip().lower()
        if label not in {'suitable', 'not_suitable'} or status not in {'shortlisted', 'review', 'rejected'}:
            excluded += 1
            continue
        actual = label == 'suitable'
        predicted = status == 'shortlisted'
        if actual and predicted: tp += 1
        elif not actual and predicted: fp += 1
        elif not actual and not predicted: tn += 1
        else: fn += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else (0.0 if precision == 0 or recall == 0 else None)
    return {
      'label_definition': 'suitable is positive; ATS shortlisted is positive prediction; review/rejected count as not shortlisted',
      'evaluated_pairs': tp + fp + tn + fn, 'excluded_unlabelled_or_invalid_pairs': excluded,
      'confusion_matrix': {'true_positive': tp, 'false_positive': fp, 'true_negative': tn, 'false_negative': fn},
      'precision': round(precision, 4) if precision is not None else None,
      'recall': round(recall, 4) if recall is not None else None,
      'f1_score': round(f1, 4) if f1 is not None else None,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    with args.input.open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    result=calculate(rows)
    result['input_file']=str(args.input)
    result['production_accuracy_claim']=False
    result['note']='Metrics only describe the supplied labelled dataset. Synthetic fixture metrics must not be presented as real-world ATS accuracy.'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
