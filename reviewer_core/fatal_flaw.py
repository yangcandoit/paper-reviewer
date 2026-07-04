from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from .quality import collect_markdown_outputs, load_issues
from .io_utils import write_json

FATAL_CUES = {
    "method not actually supporting claimed contribution": re.compile(r"\b(method|approach).{0,80}\b(does not|cannot|fails? to|not actually).{0,80}\b(support|establish|justify|contribution|claim)\b", re.I),
    "core novelty not established": re.compile(r"\b(novelty|novel|contribution|prior work).{0,80}\b(not established|unclear|not shown|incremental|already)\b", re.I),
    "baseline too weak": re.compile(r"\b(baseline|comparison).{0,80}\b(weak|missing|inadequate|unfair|straw)\b", re.I),
    "ablation not isolating contribution": re.compile(r"\b(ablation|isolate|component).{0,80}\b(missing|does not|not isolate|confound)\b", re.I),
    "evaluation leakage": re.compile(r"\b(evaluation|test|validation).{0,80}\b(leak|leakage|contaminat|train)\b", re.I),
    "dataset leakage": re.compile(r"\b(dataset|data|benchmark).{0,80}\b(leak|leakage|contaminat|duplicate)\b", re.I),
    "statistics not supporting conclusion": re.compile(r"\b(statistic|significance|variance|confidence interval|p-value|conclusion).{0,100}\b(not support|unsupported|missing|insufficient)\b", re.I),
    "visual evidence not supporting textual claim": re.compile(r"\b(figure|table|visual|plot).{0,100}\b(not support|inconsistent|unreadable|mismatch|overclaim)\b", re.I),
    "citation not supporting related-work claim": re.compile(r"\b(citation|reference|related work|prior work).{0,100}\b(not support|misrepresent|unsupported|missing)\b", re.I),
    "unfixable or hard-to-fix paper-level weakness": re.compile(r"\b(unfixable|hard to fix|paper-level|fatal|reject|major redesign|new experiment required)\b", re.I),
}

FIX_MAP = {
    "new experiment": "new_experiment",
    "new analysis": "new_analysis",
    "rewrite": "rewrite",
    "limitation": "limitation",
    "verification needed": "requires_verification",
}


def _issue_blob(issue: Any) -> str:
    return " ".join(str(getattr(issue, name, "") or "") for name in [
        "title", "claim_attacked", "reviewer_concern", "why_reviewer_cares", "required_action", "notes", "fix_type", "evidence_location"
    ])


def _failure_mode(text: str) -> str | None:
    for name, pattern in FATAL_CUES.items():
        if pattern.search(text):
            return name
    return None


def _confidence(value: str) -> str:
    low = (value or "").strip().lower()
    return low if low in {"high", "medium", "low"} else "low"


def _fix_type(issue: Any) -> str:
    if getattr(issue, "evidence_type", "") in {"information_gap", "requires_verification"}:
        return "requires_verification"
    raw = str(getattr(issue, "fix_type", "") or "").strip().lower()
    return FIX_MAP.get(raw, "requires_verification" if "verif" in raw else "rewrite")


def _severity(issue: Any, text: str, failure: str | None) -> str:
    sev = str(getattr(issue, "severity", "") or "").upper()
    if sev in {"P0", "P1", "P2"}:
        return sev
    if re.search(r"\b(fatal|unfixable|leakage|invalid)\b", text, re.I):
        return "P1"
    if failure:
        return "P2"
    return "P2"


def build_fatal_flaw_matrix(review_paths_or_dir: list[Path], max_entries: int = 100) -> dict[str, Any]:
    paths: list[Path] = []
    for item in review_paths_or_dir:
        item = Path(item)
        if item.is_dir():
            paths.extend(collect_markdown_outputs(item))
        elif item.is_file():
            paths.append(item)
    issues = load_issues(paths)
    entries: list[dict[str, Any]] = []
    for issue in issues:
        text = _issue_blob(issue)
        failure = _failure_mode(text)
        severity = _severity(issue, text, failure)
        if severity not in {"P0", "P1"} and not failure:
            continue
        if severity == "P2" and not failure:
            continue
        evidence_type = str(getattr(issue, "evidence_type", "") or "")
        fix_type = _fix_type(issue)
        if evidence_type in {"information_gap", "requires_verification"}:
            fix_type = "requires_verification"
        entry = {
            "issue_id": f"FATAL-{len(entries)+1:03d}",
            "source_issue_id": getattr(issue, "issue_id", ""),
            "severity": severity,
            "confidence": _confidence(str(getattr(issue, "confidence", "low"))),
            "evidence_location": getattr(issue, "evidence_location", "") or "requires_verification",
            "claim_attacked": getattr(issue, "claim_attacked", "") or getattr(issue, "title", ""),
            "failure_mode": failure or "major reviewer concern requires verification",
            "why_it_matters": getattr(issue, "why_reviewer_cares", "") or getattr(issue, "reviewer_concern", "") or "This concern may affect whether the manuscript's central claims are supportable.",
            "fix_type": fix_type,
            "required_action": getattr(issue, "required_action", "") or "Verify the evidence and decide whether a new analysis, experiment, limitation, or rewrite is required.",
            "risk_if_unfixed": getattr(issue, "expected_impact", "") or "High risk of reviewer rejection or major revision if the concern is confirmed.",
        }
        entries.append(entry)
        if len(entries) >= max_entries:
            break
    return {
        "version": "v1-pre2-fatal-flaw-matrix",
        "status": "ok" if entries else "no_fatal_flaws_asserted",
        "diagnostic_note": "This matrix summarizes fatal/major concerns already present in review outputs. It does not invent fatal flaws when evidence is absent.",
        "entry_count": len(entries),
        "entries": entries,
    }


def write_fatal_flaw_matrix(review_paths_or_dir: list[Path], out_dir: Path) -> dict[str, Any]:
    report = build_fatal_flaw_matrix(review_paths_or_dir)
    out = Path(out_dir) / "diagnostics"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "fatal_flaw_matrix.json", report)
    lines = [
        "# Fatal Flaw Matrix",
        "",
        "This diagnostic lists only fatal or major concerns grounded in existing review outputs. Absence of entries is not proof that the manuscript has no serious problems.",
        "",
        f"Status: `{report['status']}`",
        f"Entry count: `{report['entry_count']}`",
        "",
        "| ID | Severity | Confidence | Failure mode | Evidence | Required action |",
        "|---|---:|---|---|---|---|",
    ]
    for item in report["entries"]:
        lines.append("| {issue_id} | {severity} | {confidence} | {failure_mode} | `{evidence}` | {action} |".format(
            issue_id=item["issue_id"], severity=item["severity"], confidence=item["confidence"],
            failure_mode=str(item["failure_mode"]).replace("|", "\\|"), evidence=str(item["evidence_location"]).replace("|", "\\|"),
            action=str(item["required_action"]).replace("|", "\\|")[:240]
        ))
    (out / "fatal_flaw_matrix.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
