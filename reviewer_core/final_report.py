from __future__ import annotations

from pathlib import Path
from typing import Any
import json

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# Read first, in this order, as the main narrative of the report.
NARRATIVE_FILES = [
    "meta_review.md",
    "patch_plan.md",
    "response_strategy_review.md",   # LLM synthesis step (full mode)
    "response_strategy_matrix.md",   # deterministic table built from the issue tracker
    "rebuttal_simulation.md",
]

# Supporting scorecards: shown after the narrative as an appendix, not the headline.
APPENDIX_FILES = [
    "review_quality_scores.md",
    "review_criticality_report.md",
    "review_focus_coverage.md",
]

# Not narrative content: superseded by the top-issues table / summary header above.
EXCLUDED_FILES = {"issue_tracker.md", "run_summary.md", "REVIEW_REPORT.md"}

# final/ files that finalize_workspace() deletes once this report is built: their
# content is now inside REVIEW_REPORT.md (summary header, Top Issues table, or the
# Quality & Coverage appendix), so keeping both a .md and a REVIEW_REPORT.md copy
# would just be two overlapping documents. Their .json siblings are kept for
# machine consumption.
REDUNDANT_AFTER_REPORT = sorted((EXCLUDED_FILES - {"REVIEW_REPORT.md"}) | set(APPENDIX_FILES))


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _score_line(final_dir: Path) -> str:
    parts = []
    quality = _load_json(final_dir / "review_quality_scores.json")
    if isinstance(quality, dict) and "overall_score" in quality:
        parts.append(f"Quality: **{quality['overall_score']}/100**")
    criticality = _load_json(final_dir / "review_criticality_report.json")
    if isinstance(criticality, dict) and "criticality_score" in criticality:
        parts.append(f"Criticality: **{criticality['criticality_score']}/100**")
    focus = _load_json(final_dir / "review_focus_coverage.json")
    if isinstance(focus, dict) and "focus_coverage_score" in focus:
        parts.append(f"Focus coverage: **{focus['focus_coverage_score']}/100**")
    return " · ".join(parts)


def _issue_table(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "No P0/P1 issues were exported. See `final/issue_tracker.csv` for the full list, if any.\n"
    rows = sorted(
        issues,
        key=lambda i: (SEVERITY_ORDER.get(str(i.get("severity", "P3")).upper(), 9), str(i.get("issue_id", ""))),
    )
    lines = [
        "| Severity | Issue | Evidence | Required action |",
        "|---|---|---|---|",
    ]
    for issue in rows:
        severity = str(issue.get("severity", "")).upper() or "?"
        title = str(issue.get("title") or issue.get("reviewer_concern") or issue.get("issue_id", "")).replace("|", "\\|").replace("\n", " ")[:140]
        evidence = str(issue.get("evidence_location", "")).replace("|", "\\|").replace("\n", " ")[:100]
        action = str(issue.get("required_action", "")).replace("|", "\\|").replace("\n", " ")[:140]
        lines.append(f"| {severity} | {title} | {evidence} | {action} |")
    return "\n".join(lines) + "\n"


def _embed(final_dir: Path, name: str, *, levels: int = 1) -> list[str]:
    path = final_dir / name
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    prefix = "#" * levels
    # Demote headings so an embedded file's own "# Title" becomes a "##"/"###"
    # section nested under this report's outline instead of colliding with it.
    demoted = "\n".join(f"{prefix}{line}" if line.startswith("#") else line for line in text.splitlines())
    if not demoted.lstrip().startswith("#"):
        title = path.stem.replace("_", " ").title()
        demoted = f"{'#' * (levels + 1)} {title}\n\n{demoted}"
    return [demoted, ""]


def build_final_report(final_dir: Path, *, mode: str = "") -> str:
    """Assemble the single consolidated review report from a finalized final/ directory.

    final/ typically accumulates 8-12 separate files (meta review, revision plan,
    issue tracker in three formats, quality/criticality/focus scorecards, response
    strategy matrix, run summary, ...) produced by independent export/audit scripts.
    This reads all of them and produces one file meant to be the only thing a human
    has to open; the originals remain in final/ for anyone who wants to trace a
    finding back to its source.
    """
    final_dir = Path(final_dir)
    summary = _load_json(final_dir / "run_summary.json") or {}
    lines: list[str] = ["# Pre-Submission Review Report", ""]

    lines.append(f"- Mode: `{summary.get('mode') or mode or 'unknown'}`")
    lines.append(f"- Status: `{summary.get('status', 'unknown')}`")
    lines.append(f"- Completed steps: `{summary.get('completed_steps', '?')}/{summary.get('total_steps', '?')}`")
    lines.append(f"- Generated: `{summary.get('finalized_at', '')}`")
    score_line = _score_line(final_dir)
    if score_line:
        lines.append(f"- {score_line}")
    warnings = summary.get("warnings") or []
    if warnings:
        lines.extend(["", "**Warnings:**"])
        lines.extend(f"- {w}" for w in warnings)
    lines.append("")

    issues_data = _load_json(final_dir / "issue_tracker.json") or {}
    issues = issues_data.get("issues", []) if isinstance(issues_data, dict) else []
    p0p1 = [i for i in issues if str(i.get("severity", "")).upper() in {"P0", "P1"}]
    lines.extend(["## Top issues (P0/P1)", "", _issue_table(p0p1)])
    remaining_count = len(issues) - len(p0p1)
    if remaining_count > 0:
        lines.append(f"_{remaining_count} additional P2/P3 issue(s) in `final/issue_tracker.csv` / `final/issue_tracker.md`._")
        lines.append("")

    covered = set(EXCLUDED_FILES) | {"issue_tracker.json", "issue_tracker.csv"}
    for name in NARRATIVE_FILES:
        block = _embed(final_dir, name)
        if block:
            lines.extend(block)
            covered.add(name)

    # Any other mode-specific deliverable not in the fixed narrative list (e.g. a
    # diagnostic/privacy/revision/research-eval mode's own required outputs) still
    # gets surfaced, so this report is complete for every mode, not just full/standard.
    covered.update(APPENDIX_FILES)
    leftover = sorted(
        p.name for p in final_dir.glob("*.md")
        if p.is_file() and p.name not in covered
    )
    for name in leftover:
        lines.extend(_embed(final_dir, name))

    appendix_blocks: list[str] = []
    for name in APPENDIX_FILES:
        appendix_blocks.extend(_embed(final_dir, name, levels=2))
    if appendix_blocks:
        lines.extend(["## Review Quality & Coverage Notes", ""])
        lines.extend(appendix_blocks)

    lines.extend([
        "## Source files",
        "",
        "This report is assembled from the files below. Open them directly for unmodified "
        "originals or to trace a finding back to its source step.",
        "",
    ])
    for p in sorted(final_dir.glob("*")):
        if p.is_file() and p.name != "REVIEW_REPORT.md":
            lines.append(f"- `final/{p.name}`")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"
