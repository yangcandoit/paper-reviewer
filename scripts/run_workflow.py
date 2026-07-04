#!/usr/bin/env python3
"""Run the pre-submission review workflow with a pluggable LLM provider.

Default provider is `mock`, which is safe offline and useful for testing. For a
real run, use an OpenAI-compatible endpoint:

  export OPENAI_API_KEY=...
  export AI_REVIEWER_MODEL=...
  python scripts/run_workflow.py --packet review_packet --provider openai-compatible

Local OpenAI-compatible servers are also supported via AI_REVIEWER_BASE_URL.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.providers import get_provider
from reviewer_core.workflow import run_workflow, list_workflow_steps, select_steps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True, type=Path, help="Review packet directory.")
    ap.add_argument("--workflow", type=Path, help="Explicit workflow YAML path. Overrides --mode.")
    ap.add_argument("--mode", default="standard", choices=["quick", "standard", "full", "visual-citation", "final-check", "diagnostic", "privacy-preview", "revision-check", "research-eval"], help="Built-in workflow mode when --workflow is not supplied.")
    ap.add_argument("--outputs", type=Path, default=Path("outputs"))
    ap.add_argument("--provider", default="mock", choices=["mock", "openai-compatible", "openai"])
    ap.add_argument("--only", nargs="*", help="Optional subset of step IDs to run.")
    ap.add_argument("--from", dest="from_step", help="Run from this step ID onward.")
    ap.add_argument("--resume", action="store_true", help="Skip steps whose output file already exists and is non-empty.")
    ap.add_argument("--dry-run", action="store_true", help="Print and save the selected execution plan without calling a model.")
    ap.add_argument("--continue-on-error", action="store_true", help="Record failed steps and continue with later selected steps.")
    ap.add_argument("--save-rendered-prompts", action="store_true", help="Save rendered prompts to outputs/rendered_prompts/ for debugging.")
    ap.add_argument("--list-steps", action="store_true", help="List workflow step IDs and exit.")
    ap.add_argument("--max-context-chars", type=int, default=120000)
    ap.add_argument("--max-previous-files", type=int, default=8, help="Maximum previous Markdown outputs to include per step.")
    ap.add_argument("--max-previous-chars-per-file", type=int, default=2500, help="Characters to include from each previous output.")
    ap.add_argument("--max-previous-output-chars", type=int, default=20000, help="Total previous-output context cap per step.")
    ap.add_argument("--max-visual-assets", type=int, default=12, help="Maximum visual assets to attach to vision-capable workflow steps. Image sending requires AI_REVIEWER_SEND_IMAGES=1.")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()

    workflow_path = args.workflow or (ROOT / "workflow" / {"quick":"quick_review.yaml", "standard":"standard_review.yaml", "full":"full_review.yaml", "visual-citation":"visual_citation_review.yaml", "final-check":"final_submission_check.yaml", "diagnostic":"diagnostic_review.yaml", "privacy-preview":"privacy_preview.yaml", "revision-check":"revision_check.yaml", "research-eval":"research_eval.yaml"}[args.mode])

    if args.list_steps:
        for step in list_workflow_steps(workflow_path):
            print(step["id"])
        return

    if args.dry_run:
        # Use mock provider for type compatibility; it will not be called.
        provider = get_provider("mock")
    else:
        provider = get_provider(args.provider)

    log = run_workflow(
        workflow_path=workflow_path,
        skill_root=ROOT,
        packet_dir=args.packet,
        outputs_dir=args.outputs,
        provider=provider,
        max_context_chars=args.max_context_chars,
        max_previous_files=args.max_previous_files,
        max_previous_chars_per_file=args.max_previous_chars_per_file,
        max_previous_output_chars=args.max_previous_output_chars,
        only_steps=set(args.only) if args.only else None,
        from_step=args.from_step,
        resume=args.resume,
        dry_run=args.dry_run,
        validate=not args.no_validate,
        continue_on_error=args.continue_on_error,
        save_rendered_prompts=args.save_rendered_prompts,
        max_visual_assets=args.max_visual_assets,
    )
    print(json.dumps(log, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
