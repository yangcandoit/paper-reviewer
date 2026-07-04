#!/usr/bin/env python3
"""Generate prior-work search queries from a local review packet.

This does not upload the manuscript. It reads the local packet, extracts a short
metadata summary from title/abstract/keywords, and writes a query plan that can
be reviewed before public metadata search.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.retrieval import build_query_plan


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate prior-work search queries from a review packet.")
    ap.add_argument("--packet", required=True, type=Path, help="Review packet directory.")
    ap.add_argument("--out", type=Path, default=None, help="Output query plan JSON. Defaults to <packet>/prior_work/query_plan.json")
    ap.add_argument("--extra-term", action="append", default=[], help="Optional additional keyword/query term to include. Can be repeated.")
    ap.add_argument("--max-queries", type=int, default=8)
    args = ap.parse_args()
    out = args.out or (args.packet / "prior_work" / "query_plan.json")
    plan = build_query_plan(args.packet, out_path=out, extra_terms=args.extra_term, max_queries=args.max_queries)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"\nWrote query plan: {out}")

if __name__ == "__main__":
    main()
