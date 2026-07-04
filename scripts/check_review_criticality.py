from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.criticality import write_criticality_report

def main() -> None:
    ap = argparse.ArgumentParser(description="Check review output for under-critical or over-positive patterns.")
    ap.add_argument("outputs", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = write_criticality_report(args.outputs, args.out)
    print(f"criticality_score={report['criticality_score']} warnings={len(report['warnings'])}")
if __name__ == "__main__": main()
