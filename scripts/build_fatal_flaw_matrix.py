#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.fatal_flaw import write_fatal_flaw_matrix

def main() -> None:
    ap = argparse.ArgumentParser(description="Build a fatal/major flaw matrix from existing review outputs.")
    ap.add_argument("paths", nargs="+", type=Path, help="Review markdown files or output directories.")
    ap.add_argument("--out", type=Path, default=Path("outputs"), help="Output root. Writes diagnostics/fatal_flaw_matrix.*")
    args = ap.parse_args()
    report = write_fatal_flaw_matrix(args.paths, args.out)
    print(f"entry_count={report['entry_count']} status={report['status']}")
if __name__ == "__main__":
    main()
