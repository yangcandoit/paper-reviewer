#!/usr/bin/env python3
"""Deduplicate machine-readable review issues across one or more outputs."""
from __future__ import annotations

import argparse
from pathlib import Path
import difflib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.validation import extract_issues


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("review_files", nargs="+", type=Path)
    ap.add_argument("--threshold", type=float, default=0.78)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    issues = []
    for path in args.review_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for issue in extract_issues(text):
            data = issue.to_dict()
            data["source_file"] = str(path)
            issues.append(data)

    groups = []
    used = set()
    for i, a in enumerate(issues):
        if i in used:
            continue
        group = [i]
        used.add(i)
        for j in range(i + 1, len(issues)):
            if j in used:
                continue
            b = issues[j]
            score = max(similarity(a.get("title", ""), b.get("title", "")), similarity(a.get("required_action", ""), b.get("required_action", "")))
            if score >= args.threshold:
                group.append(j)
                used.add(j)
        groups.append(group)

    result = {"groups": [[issues[idx] for idx in group] for group in groups], "input_issue_count": len(issues), "group_count": len(groups)}
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
