from __future__ import annotations

from pathlib import Path
from typing import Any
import csv

from .models import ReviewIssue
from .quality import collect_markdown_outputs, load_issues
from .io_utils import write_json

TRACKER_FIELDS = [
    "issue_id",
    "title",
    "severity",
    "confidence",
    "evidence_type",
    "evidence_location",
    "fix_type",
    "new_experiment_needed",
    "status",
    "source_reviewer",
    "claim_attacked",
    "reviewer_concern",
    "why_reviewer_cares",
    "required_action",
    "expected_impact",
    "suggested_rewrite",
    "notes",
]


CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_formula(value: Any) -> Any:
    """Return a CSV-safe value for spreadsheet applications.

    Reviewer-generated text is untrusted: it can be influenced by manuscript
    content and then exported to issue_tracker.csv for manual triage. Spreadsheet
    apps may interpret cells beginning with =, +, -, @, tab, or carriage return
    as formulas. Prefix those string values with a single quote so they remain
    literal text. JSON/Markdown exports keep the original text.
    """
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return "'" + value
    return value


def issue_to_row(issue: ReviewIssue) -> dict[str, Any]:
    data = issue.to_dict()
    return {field: data.get(field, "") for field in TRACKER_FIELDS}


def csv_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: escape_csv_formula(row.get(field, "")) for field in TRACKER_FIELDS}


def build_issue_tracker(paths_or_dir: list[Path]) -> list[dict[str, Any]]:
    paths: list[Path] = []
    for item in paths_or_dir:
        if item.is_dir():
            paths.extend(collect_markdown_outputs(item))
        elif item.is_file():
            paths.append(item)
    issues = load_issues(paths)
    rows = [issue_to_row(issue) for issue in issues]
    rows.sort(key=lambda row: (str(row.get("severity", "")), str(row.get("issue_id", ""))))
    return rows


def write_tracker(rows: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "issue_tracker.json", {"issues": rows})
    with (out_dir / "issue_tracker.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        writer.writerows(csv_safe_row(row) for row in rows)
    lines = [
        "# Issue Tracker",
        "",
        "| ID | Severity | Status | Evidence | Fix type | Title | Required action |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        action = str(row.get("required_action", "")).replace("|", "\\|").replace("\n", " ")[:220]
        title = str(row.get("title", "")).replace("|", "\\|").replace("\n", " ")[:120]
        evidence = str(row.get("evidence_location", "")).replace("|", "\\|").replace("\n", " ")[:120]
        lines.append(
            f"| {row.get('issue_id','')} | {row.get('severity','')} | {row.get('status','')} | {evidence} | {row.get('fix_type','')} | {title} | {action} |"
        )
    (out_dir / "issue_tracker.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
