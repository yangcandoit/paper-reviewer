#!/usr/bin/env python3
"""Summarize independent reviewer outputs and issue overlap for panel synthesis."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.validation import extract_issues, validate_file


def headings(text: str) -> list[str]:
    return [line.strip("# ").strip() for line in text.splitlines() if line.startswith("#")][:30]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("review_files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("outputs/panel_index.json"))
    args = ap.parse_args()
    outputs = []
    for path in args.review_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        issues = extract_issues(text)
        outputs.append({
            "file": str(path),
            "chars": len(text),
            "headings": headings(text),
            "issue_count": len(issues),
            "p0_count": sum(1 for i in issues if i.severity == "P0"),
            "p1_count": sum(1 for i in issues if i.severity == "P1"),
            "validation": validate_file(path),
        })
    result = {"panel_outputs": outputs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
