#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.response_strategy import write_response_strategy

def main() -> None:
    ap = argparse.ArgumentParser(description="Build pre-submission response strategy planning matrix from issue outputs.")
    ap.add_argument("paths", nargs="+", type=Path, help="Issue tracker JSON, review markdown, or outputs directory.")
    ap.add_argument("--out", type=Path, default=Path("response_strategy"))
    args = ap.parse_args()
    report = write_response_strategy(args.paths, args.out)
    print(f"entry_count={report['entry_count']}")
if __name__ == "__main__":
    main()
