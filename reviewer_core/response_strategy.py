from __future__ import annotations

from pathlib import Path
from typing import Any

from .quality import collect_markdown_outputs, load_issues
from .issue_tracker import build_issue_tracker
from .io_utils import write_json


def _rows(paths_or_dir: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in paths_or_dir:
        item = Path(item)
        if item.is_file() and item.suffix.lower() == ".json":
            try:
                import json
                data = json.loads(item.read_text(encoding="utf-8"))
                rows.extend(data.get("issues", data if isinstance(data, list) else []))
            except Exception:
                pass
        elif item.exists():
            rows.extend(build_issue_tracker([item]))
    return [r for r in rows if isinstance(r, dict)]


def build_response_strategy(paths_or_dir: list[Path]) -> dict[str, Any]:
    strategies: list[dict[str, Any]] = []
    for row in _rows(paths_or_dir):
        concern = row.get("reviewer_concern") or row.get("title") or row.get("claim_attacked") or "Reviewer concern requires clarification."
        severity = str(row.get("severity", ""))
        should_fix = severity in {"P0", "P1", "P2"}
        required = row.get("required_action") or "Revise the manuscript before submission and verify evidence."
        strategies.append({
            "reviewer_concern": concern,
            "source_issue_id": row.get("issue_id", ""),
            "manuscript_side_fix": required,
            "possible_response_strategy": "After making the manuscript-side fix, explain the exact change, cite the revised section/figure/table, and acknowledge any remaining limitation without overstating the result.",
            "evidence_required": row.get("evidence_location") or "Concrete manuscript anchor or new evidence required.",
            "risk_if_not_fixed": row.get("expected_impact") or "The concern may recur in external peer review.",
            "should_fix_before_submission": should_fix,
        })
    return {
        "version": "v1-pre2-response-strategy",
        "purpose": "Pre-submission planning for transparent fixes, not deceptive rebuttal generation.",
        "entry_count": len(strategies),
        "entries": strategies,
    }


def write_response_strategy(paths_or_dir: list[Path], out_dir: Path) -> dict[str, Any]:
    report = build_response_strategy(paths_or_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "response_strategy_matrix.json", report)
    lines = [
        "# Response Strategy Matrix",
        "",
        "Use this before submission to decide what to fix in the manuscript. It is not intended to generate evasive rebuttals.",
        "",
        "| Concern | Fix before submission | Evidence required | Strategy |",
        "|---|---:|---|---|",
    ]
    for entry in report["entries"]:
        concern = str(entry["reviewer_concern"]).replace("|", "\\|")[:220]
        evidence = str(entry["evidence_required"]).replace("|", "\\|")[:180]
        strategy = str(entry["possible_response_strategy"]).replace("|", "\\|")[:220]
        lines.append(f"| {concern} | {entry['should_fix_before_submission']} | {evidence} | {strategy} |")
    (out / "response_strategy_matrix.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
