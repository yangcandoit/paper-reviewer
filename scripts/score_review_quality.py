#!/usr/bin/env python3
"""Score review-output hygiene and actionability.

This is a heuristic quality gate. It does not decide whether the review is
scientifically correct; it checks whether outputs are structured, anchored,
specific, and actionable enough to be useful.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.quality import collect_markdown_outputs, score_review_outputs, write_quality_report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path, help="Output directory or Markdown files to score.")
    ap.add_argument("--out", type=Path, default=None, help="Directory to write review_quality_scores.json/md. Defaults to first input dir or current directory.")
    args = ap.parse_args()
    paths: list[Path] = []
    for item in args.inputs:
        if item.is_dir():
            paths.extend(collect_markdown_outputs(item))
        else:
            paths.append(item)
    report = score_review_outputs(paths)
    out_dir = args.out or (args.inputs[0] if args.inputs[0].is_dir() else Path.cwd())
    write_quality_report(out_dir, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
