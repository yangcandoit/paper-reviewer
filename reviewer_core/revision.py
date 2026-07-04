from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import difflib
import json
import re

from .io_utils import TEXT_EXTS, read_text, write_json
from .issue_tracker import escape_csv_formula

CLAIM_RE = re.compile(r"\b(novel|first|best|outperform|significant|prove|demonstrate|state-of-the-art|substantial)\b", re.I)
EVIDENCE_RE = re.compile(r"\b(experiment|baseline|ablation|figure|table|statistic|confidence interval|p-value|dataset|metric|result)\b", re.I)


def _read_input_text(path: Path, max_chars: int = 300000) -> str:
    path = Path(path)
    if path.is_file():
        return read_text(path, max_chars=max_chars)
    patterns = [
        "derived/resolved_manuscript.tex", "derived/pdf/extracted_pdf.md",
        "derived/docx/extracted_docx.md", "derived/doc/extracted_doc.md", "manuscript.md",
        "sections/**/*.md", "sections/**/*.tex", "derived/sections/*.md", "*.md", "*.tex"
    ]
    chunks: list[str] = []
    total = 0
    seen: set[Path] = set()
    for pattern in patterns:
        for item in sorted(path.glob(pattern)):
            if not item.is_file() or item in seen or item.suffix.lower() not in TEXT_EXTS.union({".tex"}):
                continue
            seen.add(item)
            text = read_text(item, max_chars=min(40000, max_chars - total))
            chunks.append(f"\n\n--- {item.name} ---\n{text}")
            total += len(text)
            if total >= max_chars:
                return "".join(chunks)[:max_chars]
    return "".join(chunks)[:max_chars]


def _load_issue_rows(path: Path) -> list[dict[str, Any]]:
    if not path or not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return [x for x in data.get("issues", []) if isinstance(x, dict)]


def compare_manuscript_versions(v1: Path, v2: Path) -> dict[str, Any]:
    t1 = _read_input_text(v1)
    t2 = _read_input_text(v2)
    lines1 = t1.splitlines()
    lines2 = t2.splitlines()
    diff = list(difflib.unified_diff(lines1, lines2, fromfile="manuscript_v1", tofile="manuscript_v2", lineterm=""))
    added = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")]
    new_overclaims = [s.strip() for s in added if CLAIM_RE.search(s) and not EVIDENCE_RE.search(s)]
    return {
        "version": "v1-pre2-revision-diff",
        "v1_chars": len(t1),
        "v2_chars": len(t2),
        "added_line_count": len(added),
        "removed_line_count": len(removed),
        "diff_preview": "\n".join(diff[:400]),
        "new_overclaim_candidates": new_overclaims[:50],
        "consistency_checks": {
            "abstract_contribution_method_results_updated_consistently": "requires_manual_review",
            "figure_table_reference_numbering_affected": "requires_manual_review" if re.search(r"Figure|Table|\\ref|\\cite|\[[0-9]+\]", "\n".join(added + removed)) else "not_detected",
            "conclusion_still_matches_evidence": "requires_manual_review",
        },
    }


def _keywords(row: dict[str, Any]) -> set[str]:
    text = " ".join(str(row.get(k, "")) for k in ["title", "claim_attacked", "reviewer_concern", "required_action"])
    words = re.findall(r"[a-z][a-z0-9_-]{3,}", text.lower())
    stop = {"this", "that", "with", "from", "need", "needs", "paper", "manuscript", "issue", "action", "required"}
    return {w for w in words if w not in stop}


def audit_issue_resolution(v1: Path, v2: Path, issue_tracker: Path) -> dict[str, Any]:
    t1 = _read_input_text(v1).lower()
    t2 = _read_input_text(v2).lower()
    rows = _load_issue_rows(issue_tracker)
    matrix: list[dict[str, Any]] = []
    for row in rows:
        terms = _keywords(row)
        present_v1 = sum(1 for t in terms if t in t1)
        present_v2 = sum(1 for t in terms if t in t2)
        severity = str(row.get("severity", ""))
        wording_changed = present_v1 != present_v2
        evidence_terms_added = bool(EVIDENCE_RE.search(t2) and not EVIDENCE_RE.search(t1))
        status = "requires_manual_review"
        if severity in {"P0", "P1"} and not evidence_terms_added and wording_changed:
            status = "wording_changed_evidence_still_unclear"
        elif present_v2 < present_v1 and evidence_terms_added:
            status = "possibly_resolved"
        elif not wording_changed:
            status = "not_detectably_resolved"
        matrix.append({
            "issue_id": row.get("issue_id", ""),
            "severity": severity,
            "title": row.get("title", ""),
            "resolution_status": status,
            "p0_p1_issue_resolved": status == "possibly_resolved" if severity in {"P0", "P1"} else "not_applicable",
            "only_wording_changed_but_evidence_missing": status == "wording_changed_evidence_still_unclear",
            "new_overclaim_introduced": False,
            "required_followup": "Manually inspect the changed manuscript sections and verify evidence anchors before marking fixed.",
        })
    diff = compare_manuscript_versions(v1, v2)
    new_overclaims = bool(diff.get("new_overclaim_candidates"))
    for item in matrix:
        item["new_overclaim_introduced"] = new_overclaims
    return {
        "version": "v1-pre2-issue-resolution",
        "issue_count": len(matrix),
        "matrix": matrix,
        "new_overclaim_candidates": diff.get("new_overclaim_candidates", []),
        "remaining_risk_count": sum(1 for m in matrix if m["resolution_status"] != "possibly_resolved"),
    }


def write_revision_diff_report(v1: Path, v2: Path, out_dir: Path) -> dict[str, Any]:
    report = compare_manuscript_versions(v1, v2)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "revision_diff_report.json", report)
    lines = [
        "# Revision Diff Report",
        "",
        f"V1 characters: `{report['v1_chars']}`",
        f"V2 characters: `{report['v2_chars']}`",
        f"Added lines: `{report['added_line_count']}`",
        f"Removed lines: `{report['removed_line_count']}`",
        "",
        "## New overclaim candidates",
        "",
    ]
    lines.extend([f"- {x}" for x in report["new_overclaim_candidates"]] or ["- None detected by heuristic scan."])
    lines.extend(["", "## Diff preview", "", "```diff", report["diff_preview"], "```"])
    (out / "revision_diff_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report


def write_issue_resolution_audit(v1: Path, v2: Path, issue_tracker: Path, out_dir: Path) -> dict[str, Any]:
    report = audit_issue_resolution(v1, v2, issue_tracker)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "issue_resolution_matrix.json", report)
    fields = ["issue_id", "severity", "title", "resolution_status", "p0_p1_issue_resolved", "only_wording_changed_but_evidence_missing", "new_overclaim_introduced", "required_followup"]
    with (out / "issue_resolution_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in report["matrix"]:
            writer.writerow({k: escape_csv_formula(row.get(k, "")) for k in fields})
    lines = [
        "# Remaining Risk Report",
        "",
        f"Issue count: `{report['issue_count']}`",
        f"Remaining risk count: `{report['remaining_risk_count']}`",
        "",
        "| Issue | Severity | Status | Follow-up |",
        "|---|---:|---|---|",
    ]
    for row in report["matrix"]:
        followup = str(row.get("required_followup")).replace("|", "\\|")
        lines.append(
            f"| `{row.get('issue_id')}` | {row.get('severity')} | {row.get('resolution_status')} | {followup} |"
        )
    (out / "remaining_risk_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
