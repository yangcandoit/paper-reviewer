#!/usr/bin/env python3
"""Validate review outputs against the JSON issue-list contract."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.validation import validate_files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    report = validate_files(args.files)
    out = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(out, encoding="utf-8")
    print(out)
    if report["summary"]["total_errors"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
