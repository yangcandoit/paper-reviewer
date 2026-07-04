from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from .validation import extract_issues
from .models import ReviewIssue
from .quality import UTILITY_MD_NAMES, dedupe_issues

TARGET_PATTERNS: dict[str, re.Pattern[str]] = {
    "problem_framing": re.compile(r"\b(problem|motivation|research question|gap|scope|objective)\b", re.I),
    "prior_research": re.compile(r"\b(prior work|related work|literature|citation|reference|comparison|state of the art|baseline paper)\b", re.I),
    "method": re.compile(r"\b(method|model|algorithm|pipeline|architecture|implementation|assumption|design choice)\b", re.I),
    "experiment": re.compile(r"\b(experiment|baseline|ablation|dataset|metric|result|evaluation|statistical|seed|variance)\b", re.I),
    "visual_evidence": re.compile(r"\b(figure|table|plot|axis|legend|caption|diagram|image|visual|curve|error bar)\b", re.I),
    "conclusion_claims": re.compile(r"\b(conclusion|claim|abstract|contribution|overclaim|unsupported)\b", re.I),
    "reproducibility_compliance": re.compile(r"\b(reproducibility|code|data availability|ethics|licen[cs]e|supplementary|checklist)\b", re.I),
    "writing_clarity": re.compile(r"\b(writing|clarity|structure|organization|readability|paragraph|sentence)\b", re.I),
}

ASPECT_PATTERNS: dict[str, re.Pattern[str]] = {
    "novelty": re.compile(r"\b(novelty|novel|original|incremental|contribution|prior work|related work)\b", re.I),
    "validity": re.compile(r"\b(valid|validity|sound|correct|evidence|support|baseline|ablation|statistical|confound)\b", re.I),
    "clarity": re.compile(r"\b(clear|clarity|unclear|explain|describe|structure|readability|ambiguous)\b", re.I),
    "significance": re.compile(r"\b(significance|impact|important|useful|practical|field|contribution)\b", re.I),
    "reproducibility": re.compile(r"\b(reproducible|implementation|code|data|parameter|seed|protocol|setting)\b", re.I),
    "presentation": re.compile(r"\b(figure|table|caption|axis|legend|format|visual|plot)\b", re.I),
    "ethics_compliance": re.compile(r"\b(ethic|privacy|consent|bias|license|policy|compliance|declaration)\b", re.I),
}

REQUIRED_TARGETS = ["prior_research", "method", "experiment", "conclusion_claims"]
REQUIRED_ASPECTS = ["novelty", "validity", "clarity", "reproducibility"]


def _issue_text(issue: ReviewIssue) -> str:
    return " ".join([
        issue.title,
        issue.claim_attacked,
        issue.reviewer_concern,
        issue.why_reviewer_cares,
        issue.required_action,
        issue.suggested_rewrite,
        issue.notes,
        issue.evidence_location,
    ])


def classify_issue(issue: ReviewIssue) -> dict[str, list[str]]:
    text = _issue_text(issue)
    targets = [name for name, pattern in TARGET_PATTERNS.items() if pattern.search(text)]
    aspects = [name for name, pattern in ASPECT_PATTERNS.items() if pattern.search(text)]
    if not targets:
        targets = ["paper_level_unspecified"]
    if not aspects:
        aspects = ["unspecified"]
    return {"targets": targets, "aspects": aspects}


def load_review_issues(outputs: Path) -> list[ReviewIssue]:
    if outputs.is_file():
        return extract_issues(outputs.read_text(encoding="utf-8", errors="replace"))
    issues: list[ReviewIssue] = []
    skip = UTILITY_MD_NAMES | {"review_focus_coverage.md"}
    for path in sorted(outputs.rglob("*.md")):
        if path.name in skip:
            continue
        issues.extend(extract_issues(path.read_text(encoding="utf-8", errors="replace")))
    return dedupe_issues(issues)


def focus_coverage_report(outputs: Path) -> dict[str, Any]:
    issues = load_review_issues(outputs)
    target_counts = {k: 0 for k in list(TARGET_PATTERNS) + ["paper_level_unspecified"]}
    aspect_counts = {k: 0 for k in list(ASPECT_PATTERNS) + ["unspecified"]}
    classified = []
    for issue in issues:
        cls = classify_issue(issue)
        for target in cls["targets"]:
            target_counts[target] = target_counts.get(target, 0) + 1
        for aspect in cls["aspects"]:
            aspect_counts[aspect] = aspect_counts.get(aspect, 0) + 1
        classified.append({"issue_id": issue.issue_id, "severity": issue.severity, "title": issue.title, "targets": cls["targets"], "aspects": cls["aspects"]})
    missing_required_targets = [name for name in REQUIRED_TARGETS if target_counts.get(name, 0) == 0]
    missing_required_aspects = [name for name in REQUIRED_ASPECTS if aspect_counts.get(name, 0) == 0]
    covered_required = (len(REQUIRED_TARGETS) - len(missing_required_targets)) + (len(REQUIRED_ASPECTS) - len(missing_required_aspects))
    total_required = len(REQUIRED_TARGETS) + len(REQUIRED_ASPECTS)
    score = round(100.0 * covered_required / total_required, 2) if total_required else 0.0
    return {
        "issue_count": len(issues),
        "focus_coverage_score": score,
        "target_counts": target_counts,
        "aspect_counts": aspect_counts,
        "missing_required_targets": missing_required_targets,
        "missing_required_aspects": missing_required_aspects,
        "classified_issues": classified,
        "interpretation": "Heuristic focus coverage based on machine-readable review issues; use as a blind-spot detector, not as scientific truth.",
    }


def write_focus_coverage(outputs: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report = focus_coverage_report(outputs)
    target_dir = out_dir or (outputs if outputs.is_dir() else outputs.parent)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "review_focus_coverage.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Review Focus Coverage", "", f"Focus coverage score: **{report['focus_coverage_score']} / 100**", f"Issue count: `{report['issue_count']}`", "", "## Missing required targets", ""]
    lines.extend([f"- `{x}`" for x in report["missing_required_targets"]] or ["- None detected"])
    lines.extend(["", "## Missing required aspects", ""])
    lines.extend([f"- `{x}`" for x in report["missing_required_aspects"]] or ["- None detected"])
    lines.extend(["", "## Target counts", "", "| Target | Count |", "|---|---:|"])
    for key, val in report["target_counts"].items():
        lines.append(f"| `{key}` | {val} |")
    lines.extend(["", "## Aspect counts", "", "| Aspect | Count |", "|---|---:|"])
    for key, val in report["aspect_counts"].items():
        lines.append(f"| `{key}` | {val} |")
    lines.extend(["", "## Guidance", "", "If novelty, prior research, experiment, or reproducibility coverage is missing, run the corresponding specialist reviewer again before trusting the meta-review."])
    (target_dir / "review_focus_coverage.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
