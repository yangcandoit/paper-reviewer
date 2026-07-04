#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.citation_claim import write_citation_claim_matrix

def main() -> None:
    ap = argparse.ArgumentParser(description="Build a citation-to-claim verification scaffold from a review packet.")
    ap.add_argument("packet", type=Path, help="Review packet directory")
    ap.add_argument("--out", type=Path, help="Output directory; defaults to packet/coverage")
    ap.add_argument("--max-items", type=int, default=250)
    args = ap.parse_args()
    report = write_citation_claim_matrix(args.packet, args.out, max_items=args.max_items)
    print(f"Citation-claim entries: {report.get('entry_count', 0)}")
    print(f"Status: {report.get('status')}")

if __name__ == "__main__":
    main()
