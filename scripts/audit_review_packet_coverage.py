#!/usr/bin/env python3
"""Write a deterministic coverage audit for a review packet."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.coverage import audit_review_packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit whether a review packet covers manuscript text, visuals, citations, references, and prior-work material.")
    parser.add_argument("packet", help="Review packet directory.")
    parser.add_argument("--no-write", action="store_true", help="Print summary only; do not write coverage files.")
    args = parser.parse_args()
    report = audit_review_packet(Path(args.packet), write_files=not args.no_write)
    print(f"Coverage status: {report.get('overall_status')}")
    print(f"Missing/weak dimensions: {report.get('missing_or_weak_count')}")
    if not args.no_write:
        print(f"Wrote: {Path(args.packet) / 'coverage' / 'coverage_report.md'}")


if __name__ == "__main__":
    main()
