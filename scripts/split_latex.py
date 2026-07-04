#!/usr/bin/env python3
"""Split a LaTeX file into line-anchored Markdown section files."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import split_latex_text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("latex_file", type=Path)
    ap.add_argument("--out", type=Path, default=Path("review_packet/derived/sections"))
    args = ap.parse_args()
    text = args.latex_file.read_text(encoding="utf-8", errors="replace")
    manifest = split_latex_text(text, args.latex_file.name, args.out)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
