#!/usr/bin/env python3
"""Build a single context file from a review packet for manual or API review."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import collect_context


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("review_packet/review_context.md"))
    ap.add_argument("--max-chars", type=int, default=120000)
    args = ap.parse_args()
    context = collect_context(args.packet, max_total_chars=args.max_chars)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(context, encoding="utf-8")
    print(f"Wrote {args.out} ({len(context)} chars)")


if __name__ == "__main__":
    main()
