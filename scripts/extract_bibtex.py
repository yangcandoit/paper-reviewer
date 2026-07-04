#!/usr/bin/env python3
"""Parse BibTeX entries into a compact JSON file."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import parse_bibtex
from reviewer_core.io_utils import write_json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bib_files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("review_packet/references/bibtex_entries.json"))
    args = ap.parse_args()
    entries = []
    for bib in args.bib_files:
        entries.extend(parse_bibtex(bib))
    data = {"entries": entries}
    write_json(args.out, data)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
