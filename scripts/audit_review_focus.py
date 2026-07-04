from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.focus import write_focus_coverage

def main() -> None:
    ap = argparse.ArgumentParser(description="Audit review focus coverage across targets/aspects.")
    ap.add_argument("outputs", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = write_focus_coverage(args.outputs, args.out)
    print(f"focus_coverage_score={report['focus_coverage_score']} issue_count={report['issue_count']}")
if __name__ == "__main__": main()
