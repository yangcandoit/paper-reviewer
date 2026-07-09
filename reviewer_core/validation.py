from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from .models import ReviewIssue

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\}|\[.*?\])\s*```", re.S)
GENERIC_RE = re.compile(r"\b(needs more detail|should be improved|unclear|more discussion is needed)\b", re.I)


def extract_json_blocks(text: str) -> list[Any]:
    blocks: list[Any] = []
    for match in JSON_BLOCK_RE.finditer(text):
        raw = match.group(1)
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    # Fallback: whole file may be JSON
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            blocks.append(json.loads(stripped))
        except json.JSONDecodeError:
            pass
    return blocks


def extract_issues_and_malformed(blocks: list[Any]) -> tuple[list[ReviewIssue], list[str]]:
    """Parse issues out of already-extracted JSON blocks, reporting drops.

    A dropped item (missing a required field like ``title``) is a schema
    violation, not an empty review — callers that need to distinguish "no
    issues" from "issues were silently discarded" should use ``malformed``
    rather than let them disappear as extract_issues() does.
    """
    issues: list[ReviewIssue] = []
    malformed: list[str] = []
    for block in blocks:
        raw_issues = block if isinstance(block, list) else block.get("issues", []) if isinstance(block, dict) else []
        for item in raw_issues:
            if not isinstance(item, dict):
                malformed.append(f"non-object issue entry: {item!r}"[:200])
                continue
            try:
                issues.append(ReviewIssue.from_dict(item))
            except TypeError as exc:
                ident = item.get("issue_id", "<no issue_id>")
                malformed.append(f"{ident}: {exc}")
    return issues, malformed


def extract_issues(text: str) -> list[ReviewIssue]:
    issues, _ = extract_issues_and_malformed(extract_json_blocks(text))
    return issues


def validate_text(text: str, path: str = "<memory>") -> dict[str, Any]:
    blocks = extract_json_blocks(text)
    issues, malformed = extract_issues_and_malformed(blocks)
    p01 = [i for i in issues if i.severity in {"P0", "P1"}]
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    for issue in issues:
        for error in issue.validation_errors():
            errors.append({"issue_id": issue.issue_id, "error": error})
        if GENERIC_RE.search(issue.required_action) and len(issue.required_action) < 80:
            warnings.append(f"{issue.issue_id}: required_action may be too generic")
    for m in malformed:
        # A schema-broken issue object dropped during parsing is a contract
        # violation, not silence: without this, it looks identical to a
        # legitimately clean review (see extract_issues_and_malformed).
        errors.append({"issue_id": None, "error": f"Malformed issue object dropped: {m}"})
    if not blocks:
        # Contract requires a JSON issue list on every reviewer output, even a
        # legitimate zero-issue review (`{"issues": []}`). No parseable JSON
        # block at all means the reviewer skipped the machine-readable layer
        # entirely, so this is a hard failure, not a warning.
        errors.append({
            "issue_id": None,
            "error": "No machine-readable JSON issue list found (required by output contract)",
        })
    elif not issues:
        warnings.append("JSON issue list present but contains zero issues")
    return {
        "file": path,
        "issue_count": len(issues),
        "p0_p1_count": len(p01),
        "errors": errors,
        "warnings": warnings,
        "gates": {
            "has_json_issue_list": bool(blocks),
            "p0_p1_evidence_gate": not any("evidence" in e["error"] for e in errors),
            "schema_gate": not errors,
        },
    }


def validate_file(path: Path) -> dict[str, Any]:
    return validate_text(path.read_text(encoding="utf-8", errors="replace"), str(path))


def validate_files(paths: list[Path]) -> dict[str, Any]:
    reports = [validate_file(p) for p in paths]
    return {
        "files": reports,
        "summary": {
            "file_count": len(reports),
            "total_issues": sum(r["issue_count"] for r in reports),
            "total_errors": sum(len(r["errors"]) for r in reports),
            "total_warnings": sum(len(r["warnings"]) for r in reports),
            "all_schema_gates_pass": all(r["gates"]["schema_gate"] for r in reports),
        },
    }
