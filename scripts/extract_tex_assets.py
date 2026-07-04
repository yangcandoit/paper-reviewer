#!/usr/bin/env python3
"""Extract table, figure, equation, algorithm and citation anchors from LaTeX."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import extract_tex_assets_from_text
from reviewer_core.io_utils import write_json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("latex_file", type=Path)
    ap.add_argument("--out", type=Path, default=Path("review_packet/derived/asset_manifest.json"))
    args = ap.parse_args()
    text = args.latex_file.read_text(encoding="utf-8", errors="replace")
    data = extract_tex_assets_from_text(text, args.latex_file.name)
    write_json(args.out, data)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
