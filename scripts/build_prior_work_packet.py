#!/usr/bin/env python3
"""Build a prior-work packet from Markdown/text/BibTeX/JSON files.

The packet is intentionally simple and local. It does not upload the manuscript
or automatically infer queries. Users provide prior-work files, BibTeX, or public
metadata JSON gathered elsewhere.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import parse_bibtex
from reviewer_core.io_utils import write_json


def infer_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    m = re.search(r"title\s*=\s*[\{\"](.+?)[\}\"]", text, re.I | re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return path.stem.replace("_", " ")


def entry_from_text(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "id": path.stem,
        "title": infer_title(text, path),
        "source_file": str(path),
        "year": "",
        "venue": "",
        "problem": "",
        "method": "",
        "datasets": "",
        "metrics": "",
        "main_results": "",
        "claimed_contributions": "",
        "limitations": "",
        "relationship_to_current_paper": "requires author assessment",
        "raw_excerpt": text[:6000],
    }


def build(files: list[Path]) -> dict:
    entries = []
    for f in files:
        if f.suffix.lower() == ".bib":
            for bib in parse_bibtex(f):
                entries.append({
                    "id": bib.get("key", ""),
                    "title": bib.get("title", ""),
                    "source_file": str(f),
                    "year": bib.get("year", ""),
                    "venue": bib.get("journal") or bib.get("booktitle", ""),
                    "doi": bib.get("doi", ""),
                    "url": bib.get("url", ""),
                    "problem": "",
                    "method": "",
                    "datasets": "",
                    "metrics": "",
                    "main_results": "",
                    "claimed_contributions": "",
                    "limitations": "",
                    "relationship_to_current_paper": "requires author assessment",
                    "raw_excerpt": "",
                })
        elif f.suffix.lower() == ".json":
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                entries.extend(data)
            elif isinstance(data, dict):
                entries.extend(data.get("prior_work_entries", data.get("entries", [])))
        else:
            entries.append(entry_from_text(f))
    return {"prior_work_entries": entries}


def write_markdown_packet(data: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = data.get("prior_work_entries", [])
    lines = [
        "# Prior-Work Packet",
        "",
        "This packet is a local, user-provided prior-work summary. Empty cells mean the author or reviewer should complete the comparison manually.",
        "",
        "| ID | Year | Title | Venue | Relationship to current paper |",
        "|---|---:|---|---|---|",
    ]
    for e in entries:
        title = str(e.get("title", "")).replace("|", "\\|")[:180]
        rel = str(e.get("relationship_to_current_paper", "requires author assessment")).replace("|", "\\|")[:160]
        lines.append(f"| {e.get('id','')} | {e.get('year','')} | {title} | {e.get('venue','')} | {rel} |")
    (out_dir / "prior_work_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    matrix = [
        "# Prior-Work Comparison Matrix",
        "",
        "| Prior work | Problem | Method | Datasets | Metrics | Main results | Difference / gap |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        matrix.append(
            "| {title} | {problem} | {method} | {datasets} | {metrics} | {results} | {rel} |".format(
                title=str(e.get("title", e.get("id", ""))).replace("|", "\\|")[:120],
                problem=str(e.get("problem", "")).replace("|", "\\|")[:120],
                method=str(e.get("method", "")).replace("|", "\\|")[:120],
                datasets=str(e.get("datasets", "")).replace("|", "\\|")[:120],
                metrics=str(e.get("metrics", "")).replace("|", "\\|")[:120],
                results=str(e.get("main_results", "")).replace("|", "\\|")[:120],
                rel=str(e.get("relationship_to_current_paper", "requires author assessment")).replace("|", "\\|")[:160],
            )
        )
    (out_dir / "comparison_matrix.md").write_text("\n".join(matrix).rstrip() + "\n", encoding="utf-8")

    questions = [
        "# Missing Literature Questions",
        "",
        "Use these questions before running the novelty and literature-gap reviewers:",
        "",
        "1. Which listed paper is closest to the current manuscript?",
        "2. Which contribution claims are not clearly distinguished from prior work?",
        "3. Which experimental baselines or datasets appear in prior work but not in the current manuscript?",
        "4. Which citations need to be discussed in the Introduction or Related Work rather than only listed in references?",
        "5. Which related work entries require manual verification before being used as reviewer evidence?",
    ]
    (out_dir / "missing_literature_questions.md").write_text("\n".join(questions) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("review_packet/prior_work_packet.json"), help="JSON output path.")
    ap.add_argument("--out-dir", type=Path, default=None, help="Optional directory for Markdown summary, matrix, and questions.")
    args = ap.parse_args()
    data = build(args.files)
    write_json(args.out, data)
    if args.out_dir:
        write_markdown_packet(data, args.out_dir)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
