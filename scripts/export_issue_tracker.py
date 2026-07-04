#!/usr/bin/env python3
"""Export machine-readable review issues into JSON, CSV, and Markdown trackers."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.issue_tracker import build_issue_tracker, write_tracker


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path, help="Output directory or Markdown files containing JSON issue lists.")
    ap.add_argument("--out", type=Path, default=Path("issue_tracker"), help="Directory for issue_tracker.json/csv/md.")
    args = ap.parse_args()
    rows = build_issue_tracker(args.inputs)
    write_tracker(rows, args.out)
    print(f"Exported {len(rows)} issues to {args.out}")


if __name__ == "__main__":
    main()
