#!/usr/bin/env python3
"""Assemble the single consolidated REVIEW_REPORT.md from a finalized final/ directory."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.final_report import build_final_report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("final_dir", type=Path, help="A workspace's final/ directory.")
    ap.add_argument("--mode", default="", help="Fallback mode label if run_summary.json is missing it.")
    ap.add_argument("--out", type=Path, default=None, help="Defaults to <final_dir>/../REVIEW_REPORT.md (the workspace root).")
    args = ap.parse_args()
    out = args.out or (args.final_dir.parent / "REVIEW_REPORT.md")
    out.write_text(build_final_report(args.final_dir, mode=args.mode), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
