#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.normalized_document import build_normalized_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized document outputs for reviewer context.")
    parser.add_argument("packet", help="Review packet directory")
    parser.add_argument("--out", default="", help="Optional output directory; defaults to packet/derived/normalized_document")
    args = parser.parse_args()
    manifest = build_normalized_document(Path(args.packet), Path(args.out) if args.out else None)
    print(f"Normalized document status: {manifest.get('status')}")
    print(f"Counts: {manifest.get('counts')}")

if __name__ == "__main__":
    main()
