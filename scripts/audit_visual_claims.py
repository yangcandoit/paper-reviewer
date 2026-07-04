#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.visual_audit import write_visual_claim_audit

def main() -> None:
    ap = argparse.ArgumentParser(description="Audit visual claims and confidence guardrails for a review packet.")
    ap.add_argument("packet", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="Output directory. Defaults to packet/coverage.")
    args = ap.parse_args()
    report = write_visual_claim_audit(args.packet, args.out)
    print(f"entry_count={report['entry_count']} asset_count={report['asset_count']}")
if __name__ == "__main__":
    main()
