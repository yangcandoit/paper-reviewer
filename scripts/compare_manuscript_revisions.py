#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.revision import write_revision_diff_report

def main() -> None:
    ap = argparse.ArgumentParser(description="Compare two manuscript versions or review packets.")
    ap.add_argument("--v1", required=True, type=Path)
    ap.add_argument("--v2", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("revision_check"))
    args = ap.parse_args()
    report = write_revision_diff_report(args.v1, args.v2, args.out)
    print(f"added={report['added_line_count']} removed={report['removed_line_count']}")
if __name__ == "__main__":
    main()
