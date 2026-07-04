from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal
import json
import re

Severity = Literal["P0", "P1", "P2", "P3"]
Confidence = Literal["High", "Medium", "Low"]
FixType = Literal[
    "rewrite",
    "argumentation",
    "new analysis",
    "new experiment",
    "citation",
    "reproducibility detail",
    "limitation",
    "policy/compliance",
    "verification needed",
    "other",
]
Status = Literal["open", "fixed", "deferred", "rejected"]

VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}
VALID_CONFIDENCES = {"High", "Medium", "Low"}
VALID_FIX_TYPES = {
    "rewrite",
    "argumentation",
    "new analysis",
    "new experiment",
    "citation",
    "reproducibility detail",
    "limitation",
    "policy/compliance",
    "verification needed",
    "other",
}
VALID_STATUSES = {"open", "fixed", "deferred", "rejected"}

ANCHOR_RE = re.compile(
    r"(section|table|figure|fig\.?|equation|appendix|paragraph|page|line|anchor|claim|L\d+|p\.\s*\d+|§)",
    re.IGNORECASE,
)

@dataclass
class ReviewIssue:
    issue_id: str
    title: str
    severity: Severity
    evidence_location: str
    confidence: Confidence
    fix_type: FixType
    required_action: str
    source_reviewer: str = ""
    claim_attacked: str = ""
    reviewer_concern: str = ""
    why_reviewer_cares: str = ""
    new_experiment_needed: bool = False
    expected_impact: str = ""
    status: Status = "open"
    evidence_type: str = "located"  # located | information_gap | requires_verification
    suggested_rewrite: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewIssue":
        defaults = {
            "source_reviewer": "",
            "claim_attacked": "",
            "reviewer_concern": "",
            "why_reviewer_cares": "",
            "new_experiment_needed": False,
            "expected_impact": "",
            "status": "open",
            "evidence_type": "located",
            "suggested_rewrite": "",
            "notes": "",
        }
        merged = {**defaults, **data}
        return cls(**merged)

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.issue_id:
            errors.append("missing issue_id")
        if not self.title:
            errors.append("missing title")
        if self.severity not in VALID_SEVERITIES:
            errors.append(f"invalid severity: {self.severity}")
        if self.confidence not in VALID_CONFIDENCES:
            errors.append(f"invalid confidence: {self.confidence}")
        if self.fix_type not in VALID_FIX_TYPES:
            errors.append(f"invalid fix_type: {self.fix_type}")
        if self.status not in VALID_STATUSES:
            errors.append(f"invalid status: {self.status}")
        if not self.required_action:
            errors.append("missing required_action")
        if self.severity in {"P0", "P1"}:
            if not self.evidence_location:
                errors.append("P0/P1 issue missing evidence_location")
            elif not ANCHOR_RE.search(self.evidence_location) and self.evidence_type == "located":
                errors.append("P0/P1 evidence_location lacks a recognizable anchor; use information_gap if not located")
            if self.evidence_type not in {"located", "information_gap", "requires_verification"}:
                errors.append("invalid evidence_type")
        return errors


@dataclass
class WorkflowStep:
    id: str
    prompt: str
    output: str
    depends_on: list[str] = field(default_factory=list)
    reviewer: str = ""


@dataclass
class PacketFile:
    path: str
    category: str
    chars: int = 0
    sha256: str = ""
    anchors: list[str] = field(default_factory=list)


def issues_to_json(issues: list[ReviewIssue]) -> str:
    return json.dumps({"issues": [i.to_dict() for i in issues]}, indent=2, ensure_ascii=False)


def load_issues_from_json(path: Path) -> list[ReviewIssue]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        raw = data
    else:
        raw = data.get("issues", [])
    return [ReviewIssue.from_dict(item) for item in raw if isinstance(item, dict)]
