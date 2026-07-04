#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.retrieval_provenance import write_retrieval_provenance

def main() -> None:
    ap = argparse.ArgumentParser(description="Build a provenance report for prior-work search hits and user-provided references.")
    ap.add_argument("packet", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="Output directory. Defaults to packet/prior_work.")
    args = ap.parse_args()
    report = write_retrieval_provenance(args.packet, args.out)
    print(f"item_count={report['item_count']} evidence_levels={report['evidence_level_counts']}")
if __name__ == "__main__":
    main()
