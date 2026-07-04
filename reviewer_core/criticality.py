from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re
from .focus import load_review_issues

PRAISE_RE = re.compile(r"\b(strong|excellent|impressive|well-written|clear contribution|novel|compelling|solid|good)\b", re.I)
WEAKNESS_RE = re.compile(r"\b(weak|missing|insufficient|unclear|unsupported|concern|limitation|overclaim|flaw|risk|threat)\b", re.I)


def check_criticality(outputs: Path) -> dict[str, Any]:
    issues = load_review_issues(outputs)
    md_texts = []
    if outputs.is_file():
        md_texts.append(outputs.read_text(encoding="utf-8", errors="replace"))
    else:
        for path in outputs.rglob("*.md"):
            if not path.name.startswith("review_criticality"):
                md_texts.append(path.read_text(encoding="utf-8", errors="replace"))
    combined = "\n".join(md_texts)
    p0p1 = [i for i in issues if i.severity in {"P0", "P1"}]
    p0 = [i for i in issues if i.severity == "P0"]
    praise_hits = len(PRAISE_RE.findall(combined))
    weakness_hits = len(WEAKNESS_RE.findall(combined))
    issue_count = len(issues)
    warnings: list[str] = []
    if issue_count == 0:
        warnings.append("No machine-readable issues found; cannot assess criticality.")
    if issue_count and len(p0p1) == 0:
        warnings.append("No P0/P1 issues found. This may be valid for a very strong manuscript, but pre-submission review should verify that major risks were actively searched for.")
    if issue_count >= 6 and len(p0p1) / issue_count < 0.15:
        warnings.append("Very low share of major issues; check for over-positive or under-critical review behavior.")
    if praise_hits > weakness_hits * 2 + 5:
        warnings.append("Praise language substantially exceeds weakness language; run adversarial and novelty reviewers again if risk discovery is the goal.")
    anchored_major = [i for i in p0p1 if i.evidence_type == "located" and i.evidence_location]
    if p0p1 and len(anchored_major) / len(p0p1) < 0.8:
        warnings.append("Less than 80% of major issues are directly anchored; ask reviewer to convert unanchored concerns into evidence-backed issues or information gaps.")
    score = 100
    score -= 20 if not p0p1 and issue_count else 0
    score -= 15 if praise_hits > weakness_hits * 2 + 5 else 0
    score -= 15 if p0p1 and len(anchored_major) / len(p0p1) < 0.8 else 0
    return {"criticality_score": max(0, score), "issue_count": issue_count, "p0_count": len(p0), "p0_p1_count": len(p0p1), "praise_signal_count": praise_hits, "weakness_signal_count": weakness_hits, "warnings": warnings, "interpretation": "Heuristic bias/criticality check. It flags overly positive or weakly anchored patterns; it does not prove review correctness."}


def write_criticality_report(outputs: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report = check_criticality(outputs)
    target_dir = out_dir or (outputs if outputs.is_dir() else outputs.parent)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "review_criticality_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Review Criticality and Positivity-Bias Check", "", f"Criticality score: **{report['criticality_score']} / 100**", "", "| Metric | Value |", "|---|---:|", f"| Issue count | {report['issue_count']} |", f"| P0 issues | {report['p0_count']} |", f"| P0/P1 issues | {report['p0_p1_count']} |", f"| Praise signal count | {report['praise_signal_count']} |", f"| Weakness signal count | {report['weakness_signal_count']} |", "", "## Warnings", ""]
    lines.extend([f"- {w}" for w in report["warnings"]] or ["- None detected"])
    lines.extend(["", "## Guidance", "", "If this report flags under-critical behavior, rerun the adversarial, novelty, experiment, and citation reviewers with stricter evidence requirements."])
    (target_dir / "review_criticality_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
