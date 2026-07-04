from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from .packet import collect_context
from .workflow import load_workflow
from .io_utils import write_json

VISION_RE = re.compile(r"visual|figure|table|image", re.I)
STRONG_RE = re.compile(r"critical|meta|novelty|method|statistics|fatal|response|revision", re.I)
CHEAP_RE = re.compile(r"packet|sanitizer|map|format|coverage", re.I)


def _bucket(chars: int) -> str:
    if chars < 25000:
        return "low"
    if chars < 80000:
        return "medium"
    if chars < 180000:
        return "high"
    return "very_high"


def estimate_workflow_cost(packet: Path, workflow_path: Path, images_enabled: bool = False) -> dict[str, Any]:
    wf = load_workflow(Path(workflow_path))
    context = collect_context(Path(packet), max_total_chars=400000)
    image_count = sum(1 for p in Path(packet).rglob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}) if images_enabled else 0
    steps = []
    for step in wf.get("steps", []):
        sid = str(step.get("id", ""))
        prompt_path = Path(workflow_path).resolve().parents[0].parent / str(step.get("prompt", ""))
        prompt_chars = 0
        if prompt_path.exists():
            prompt_chars = len(prompt_path.read_text(encoding="utf-8", errors="replace"))
        est = len(context) + prompt_chars
        needs_vision = bool(step.get("uses_visual_assets")) or bool(VISION_RE.search(sid))
        strongest = bool(STRONG_RE.search(sid))
        cheaper_ok = bool(CHEAP_RE.search(sid)) and not strongest
        steps.append({
            "id": sid,
            "estimated_context_chars": est,
            "context_size_category": _bucket(est),
            "requires_vision_capable_model": needs_vision,
            "requires_strongest_reasoning": strongest,
            "can_use_cheaper_model": cheaper_ok,
            "relative_cost_category": "very_high" if needs_vision and images_enabled else "high" if strongest or _bucket(est) in {"high", "very_high"} else "medium" if _bucket(est) == "medium" else "low",
        })
    return {
        "version": "v1-pre2-cost-estimate",
        "workflow": wf.get("name", Path(workflow_path).name),
        "step_count": len(steps),
        "base_context_chars": len(context),
        "image_count_if_enabled": image_count,
        "uses_user_editable_relative_costs_only": True,
        "steps": steps,
    }


def write_workflow_cost_estimate(packet: Path, workflow_path: Path, out_dir: Path, images_enabled: bool = False) -> dict[str, Any]:
    report = estimate_workflow_cost(packet, workflow_path, images_enabled=images_enabled)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "model_task_plan.json", report)
    lines = [
        "# Workflow Cost Estimate",
        "",
        "This is a rough local size and model-planning estimate. It does not hard-code vendor prices.",
        "",
        f"Workflow: `{report['workflow']}`",
        f"Steps: `{report['step_count']}`",
        f"Base context characters: `{report['base_context_chars']}`",
        f"Image count if enabled: `{report['image_count_if_enabled']}`",
        "",
        "| Step | Context | Vision | Strong reasoning | Cheaper model OK | Relative cost |",
        "|---|---|---:|---:|---:|---|",
    ]
    for s in report["steps"]:
        lines.append(f"| `{s['id']}` | {s['context_size_category']} | {s['requires_vision_capable_model']} | {s['requires_strongest_reasoning']} | {s['can_use_cheaper_model']} | {s['relative_cost_category']} |")
    (out / "workflow_cost_estimate.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
