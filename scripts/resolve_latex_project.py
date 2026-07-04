#!/usr/bin/env python3
"""Resolve a LaTeX project into one manuscript file plus included-file manifest."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import resolve_latex_project
from reviewer_core.io_utils import write_json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("main_tex", type=Path)
    ap.add_argument("--out", type=Path, default=Path("review_packet/derived/resolved_manuscript.tex"))
    ap.add_argument("--manifest", type=Path, default=Path("review_packet/derived/latex_inputs.json"))
    args = ap.parse_args()
    text, included = resolve_latex_project(args.main_tex)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    write_json(args.manifest, {"main": str(args.main_tex), "included": included})
    print(f"Wrote {args.out}")
    print(f"Included records: {len(included)}")


if __name__ == "__main__":
    main()
