#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.revision import write_issue_resolution_audit

def main() -> None:
    ap = argparse.ArgumentParser(description="Audit whether issue tracker entries appear resolved across manuscript revisions.")
    ap.add_argument("--v1", required=True, type=Path)
    ap.add_argument("--v2", required=True, type=Path)
    ap.add_argument("--issue-tracker", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("revision_check"))
    args = ap.parse_args()
    report = write_issue_resolution_audit(args.v1, args.v2, args.issue_tracker, args.out)
    print(f"issue_count={report['issue_count']} remaining_risk_count={report['remaining_risk_count']}")
if __name__ == "__main__":
    main()
