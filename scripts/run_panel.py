#!/usr/bin/env python3
"""Run the workflow as a simple multi-provider reviewer panel.

This is still a local Skill workflow, not a SaaS. Each panel member writes into
its own output directory. Use `mock:name` for offline tests or
`openai-compatible:name[:model]` for a configured OpenAI-compatible endpoint.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.providers import MockProvider, OpenAICompatibleProvider
from reviewer_core.workflow import run_workflow
from reviewer_core.quality import collect_markdown_outputs, score_review_outputs, write_quality_report
from reviewer_core.issue_tracker import build_issue_tracker, write_tracker
from reviewer_core.io_utils import write_json


def provider_from_spec(spec: str):
    parts = spec.split(":")
    kind = parts[0].strip().lower()
    name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else kind
    if kind in {"mock", "offline"}:
        return name, MockProvider(reviewer_name=name)
    if kind in {"openai", "openai-compatible", "compatible"}:
        provider = OpenAICompatibleProvider.from_env()
        if len(parts) > 2 and parts[2].strip():
            provider.model = parts[2].strip()
        return name, provider
    raise ValueError(f"Unsupported panel provider spec: {spec}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True, type=Path)
    ap.add_argument("--workflow", type=Path, default=ROOT / "workflow" / "standard_review.yaml")
    ap.add_argument("--outputs", type=Path, default=Path("panel_outputs"))
    ap.add_argument("--providers", nargs="+", default=["mock:reviewer_a", "mock:reviewer_b"], help="Provider specs, e.g. mock:a openai-compatible:b:gpt-4.1-mini")
    ap.add_argument("--only", nargs="*", help="Optional subset of step IDs to run for each panel member.")
    ap.add_argument("--from", dest="from_step", help="Run from this step onward for each panel member.")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-context-chars", type=int, default=120000)
    args = ap.parse_args()

    args.outputs.mkdir(parents=True, exist_ok=True)
    panel_log = {"panel_members": [], "outputs": str(args.outputs)}
    all_member_dirs: list[Path] = []
    for spec in args.providers:
        name, provider = provider_from_spec(spec)
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name)
        out_dir = args.outputs / safe_name
        log = run_workflow(
            workflow_path=args.workflow,
            skill_root=ROOT,
            packet_dir=args.packet,
            outputs_dir=out_dir,
            provider=provider,
            max_context_chars=args.max_context_chars,
            only_steps=set(args.only) if args.only else None,
            from_step=args.from_step,
            resume=args.resume,
        )
        all_member_dirs.append(out_dir)
        panel_log["panel_members"].append({"name": name, "provider_spec": spec, "output_dir": str(out_dir), "status": log.get("status")})

    md_paths = []
    for out_dir in all_member_dirs:
        md_paths.extend(collect_markdown_outputs(out_dir))
    quality = score_review_outputs(md_paths)
    write_json(args.outputs / "panel_log.json", panel_log)
    write_json(args.outputs / "panel_quality_scores.json", quality)
    rows = build_issue_tracker(all_member_dirs)
    write_tracker(rows, args.outputs / "issue_tracker")

    lines = [
        "# Panel Summary",
        "",
        f"Panel members: {len(panel_log['panel_members'])}",
        f"Total machine-readable issues: {quality['counts']['issue_count']}",
        f"Review quality score: {quality['overall_score']} / 100",
        "",
        "| Member | Status | Output directory |",
        "|---|---|---|",
    ]
    for member in panel_log["panel_members"]:
        lines.append(f"| {member['name']} | {member['status']} | `{member['output_dir']}` |")
    (args.outputs / "panel_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps(panel_log, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
