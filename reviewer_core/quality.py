from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import math
import re

from .models import ReviewIssue
from .validation import extract_issues, validate_file
from .io_utils import write_json

NOVELTY_RE = re.compile(r"\b(novelty|novel|prior work|related work|literature|incremental|contribution)\b", re.I)
EXPERIMENT_RE = re.compile(r"\b(experiment|baseline|ablation|metric|dataset|result|statistical|variance|seed)\b", re.I)
ACTION_VERBS_RE = re.compile(r"\b(add|rewrite|revise|compare|report|include|remove|verify|clarify|justify|run|provide|explain|state|cite)\b", re.I)
GENERIC_ACTION_RE = re.compile(r"\b(needs more detail|should be improved|more discussion is needed|unclear|improve clarity)\b", re.I)


def issue_text(issue: ReviewIssue) -> str:
    return " ".join([
        issue.title,
        issue.claim_attacked,
        issue.reviewer_concern,
        issue.why_reviewer_cares,
        issue.required_action,
        issue.suggested_rewrite,
        issue.notes,
    ])


_SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _evidence_key(issue: ReviewIssue) -> str:
    return re.sub(r"\s+", " ", (issue.evidence_location or "").strip().lower())


def dedupe_issues(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    """Collapse issues that share an identical evidence anchor into one row.

    Several pipeline steps (severity calibration, revision-pass merging, rebuttal
    rehearsal) restate an earlier specialist finding under a new issue_id instead
    of amending it in place, so the same underlying problem gets counted once per
    restatement. Grouping is intentionally conservative -- exact evidence_location
    match only, case/whitespace-insensitive -- so two distinct issues that merely
    cite nearby (but not identical) lines are never wrongly merged. Keeps the
    highest-severity copy in the group, since a later calibration step upgrading
    P1 to P0 must win over the original.
    """
    groups: dict[str, list[ReviewIssue]] = {}
    order: list[str] = []
    for issue in issues:
        key = _evidence_key(issue)
        if not key:
            key = f"__no_anchor__{issue.issue_id}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(issue)

    deduped: list[ReviewIssue] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            deduped.append(group[0])
            continue
        best = min(group, key=lambda i: _SEVERITY_RANK.get(i.severity, 9))
        others = [i.issue_id for i in group if i is not best]
        if others:
            note = f"Also raised independently as: {', '.join(others)}."
            best.notes = f"{best.notes} {note}".strip() if best.notes else note
        deduped.append(best)
    return deduped


def load_issues(paths: list[Path]) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for path in paths:
        if path.is_file():
            issues.extend(extract_issues(path.read_text(encoding="utf-8", errors="replace")))
    return dedupe_issues(issues)


UTILITY_MD_NAMES = {
    "run_summary.md",
    "review_quality_scores.md",
    "issue_tracker.md",
    "panel_summary.md",
}


def collect_markdown_outputs(outputs_dir: Path) -> list[Path]:
    if outputs_dir.is_file():
        return [outputs_dir]
    return sorted(
        p
        for p in outputs_dir.rglob("*.md")
        if p.is_file() and not p.name.startswith(".") and p.name not in UTILITY_MD_NAMES
    )


def _pct(numer: int, denom: int) -> float:
    return round((100.0 * numer / denom), 2) if denom else 0.0


def score_review_outputs(paths: list[Path]) -> dict[str, Any]:
    issues = load_issues(paths)
    validations = [validate_file(p) for p in paths if p.is_file()]
    severity_counts = {sev: 0 for sev in ["P0", "P1", "P2", "P3"]}
    evidence_counts = {"located": 0, "information_gap": 0, "requires_verification": 0, "other": 0}
    actionable = 0
    generic_actions = 0
    novelty = 0
    experiment = 0
    anchored_p01 = 0
    total_p01 = 0
    exact_titles: dict[str, int] = {}

    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        evidence_counts[issue.evidence_type] = evidence_counts.get(issue.evidence_type, 0) + 1
        if issue.severity in {"P0", "P1"}:
            total_p01 += 1
            if issue.evidence_type == "located" and issue.evidence_location:
                anchored_p01 += 1
        if ACTION_VERBS_RE.search(issue.required_action) and len(issue.required_action.strip()) >= 50:
            actionable += 1
        if GENERIC_ACTION_RE.search(issue.required_action):
            generic_actions += 1
        text = issue_text(issue)
        if NOVELTY_RE.search(text):
            novelty += 1
        if EXPERIMENT_RE.search(text):
            experiment += 1
        normalized_title = re.sub(r"\W+", " ", issue.title.lower()).strip()
        if normalized_title:
            exact_titles[normalized_title] = exact_titles.get(normalized_title, 0) + 1

    duplicate_issue_count = sum(count - 1 for count in exact_titles.values() if count > 1)
    total_errors = sum(len(v.get("errors", [])) for v in validations)
    total_warnings = sum(len(v.get("warnings", [])) for v in validations)
    file_count = len(paths)
    issue_count = len(issues)

    evidence_score = _pct(anchored_p01, total_p01) if total_p01 else 100.0
    actionability_score = _pct(actionable, issue_count) if issue_count else 0.0
    schema_score = max(0.0, 100.0 - min(100.0, total_errors * 12.5))
    specificity_penalty = min(30.0, generic_actions * 5.0 + duplicate_issue_count * 3.0)
    coverage_score = 0.0
    if issue_count:
        coverage_components = [
            50.0 if novelty else 0.0,
            50.0 if experiment else 0.0,
        ]
        coverage_score = sum(coverage_components)
    overall = round(max(0.0, min(100.0, (
        0.30 * evidence_score
        + 0.25 * actionability_score
        + 0.25 * schema_score
        + 0.20 * coverage_score
        - specificity_penalty
    ))), 2)

    return {
        "overall_score": overall,
        "subscores": {
            "p0_p1_evidence_score": evidence_score,
            "actionability_score": actionability_score,
            "schema_score": round(schema_score, 2),
            "coverage_score": round(coverage_score, 2),
            "specificity_penalty": round(specificity_penalty, 2),
        },
        "counts": {
            "file_count": file_count,
            "issue_count": issue_count,
            "p0_p1_count": total_p01,
            "anchored_p0_p1_count": anchored_p01,
            "total_validation_errors": total_errors,
            "total_validation_warnings": total_warnings,
            "generic_action_count": generic_actions,
            "duplicate_title_count": duplicate_issue_count,
            "novelty_related_issue_count": novelty,
            "experiment_related_issue_count": experiment,
        },
        "severity_counts": severity_counts,
        "evidence_type_counts": evidence_counts,
        "validation_reports": validations,
    }


def write_quality_report(outputs_dir: Path, report: dict[str, Any]) -> None:
    write_json(outputs_dir / "review_quality_scores.json", report)
    lines = [
        "# Review Quality Scores",
        "",
        f"Overall score: **{report['overall_score']} / 100**",
        "",
        "## Subscores",
        "",
        "| Metric | Score |",
        "|---|---:|",
    ]
    for key, value in report["subscores"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Counts", "", "| Metric | Count |", "|---|---:|"])
    for key, value in report["counts"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Severity counts", "", "| Severity | Count |", "|---|---:|"])
    for key, value in report["severity_counts"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This heuristic score checks review hygiene, not scientific truth. A high score means the outputs are more structured, anchored, and actionable; it does not guarantee that the criticisms are correct.",
    ])
    (outputs_dir / "review_quality_scores.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
