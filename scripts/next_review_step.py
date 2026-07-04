#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.agent_native import list_steps, mark_completed, reset_step, write_next_step


def print_steps(steps: list[dict]) -> None:
    for step in steps:
        print("{step_id}\t{status}\t{prompt}\t{expected_output}".format(**step))


def main() -> None:
    ap = argparse.ArgumentParser(description="Show or update the next agent-native review step.")
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--mark-completed", help="Mark a step completed and advance NEXT_STEP.md.")
    ap.add_argument("--reset-step", help="Reset a step to pending and refresh NEXT_STEP.md.")
    ap.add_argument("--allow-missing-output", action="store_true", help="Allow marking completed even if the expected output is missing or empty.")
    ap.add_argument("--force", action="store_true", help="Alias for --allow-missing-output.")
    ap.add_argument("--list", action="store_true", help="List all workflow steps and statuses.")
    ap.add_argument("--json", action="store_true", help="Print machine-readable JSON for the selected action.")
    args = ap.parse_args()

    if args.mark_completed:
        allow_missing = bool(args.allow_missing_output or args.force)
        try:
            result = mark_completed(args.workspace, args.mark_completed, allow_missing_output=allow_missing)
        except Exception as exc:
            if args.json:
                print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Marked completed: {args.mark_completed}")
            if allow_missing:
                print("Warning: marked completed without verifying a non-empty expected output.")
            if result.get("step_id"):
                print(f"Next step: {result['step_id']}")
            else:
                print(result.get("message", "No pending steps."))
        return
    if args.reset_step:
        result = reset_step(args.workspace, args.reset_step)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Reset step: {args.reset_step}")
            if result.get("step_id"):
                print(f"Next step: {result['step_id']}")
        return
    if args.list:
        steps = list_steps(args.workspace)
        if args.json:
            print(json.dumps(steps, indent=2))
        else:
            print_steps(steps)
        return
    result = write_next_step(args.workspace, skill_root=ROOT, mark_in_progress=True)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("step_id"):
            print(f"Next step: {result['step_id']}")
            print(f"Prompt: {result['prompt']}")
            print(f"Expected output: {result['expected_output']}")
            print(f"Step file: {args.workspace.resolve() / result['step_file']}")
        else:
            print(result.get("message", "No pending steps."))


if __name__ == "__main__":
    main()
