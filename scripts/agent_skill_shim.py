#!/usr/bin/env python3
from __future__ import annotations

"""Small dispatcher for agent-native skill workflows.

This script is convenience glue only. It does not call model providers.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.agent_native import MODE_TO_WORKFLOW, create_workspace, finalize_workspace, list_steps, mark_completed, reset_step, write_next_step


def main() -> None:
    ap = argparse.ArgumentParser(description="Agent-native skill shim for Codex / Claude Code.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--mode", default="standard", choices=sorted(MODE_TO_WORKFLOW))
    p.add_argument("--overwrite", action="store_true")
    n = sub.add_parser("next")
    n.add_argument("--workspace", required=True, type=Path)
    l = sub.add_parser("list")
    l.add_argument("--workspace", required=True, type=Path)
    m = sub.add_parser("mark-completed")
    m.add_argument("--workspace", required=True, type=Path)
    m.add_argument("step_id")
    r = sub.add_parser("reset-step")
    r.add_argument("--workspace", required=True, type=Path)
    r.add_argument("step_id")
    f = sub.add_parser("finalize")
    f.add_argument("--workspace", required=True, type=Path)
    args = ap.parse_args()
    if args.cmd == "prepare":
        state = create_workspace(input_path=args.input, workspace=args.workspace, mode=args.mode, skill_root=ROOT, overwrite=args.overwrite)
        print(f"prepared {args.workspace.resolve()} with {len(state['steps'])} steps")
    elif args.cmd == "next":
        print(write_next_step(args.workspace, skill_root=ROOT, mark_in_progress=True))
    elif args.cmd == "list":
        for step in list_steps(args.workspace):
            print(f"{step['step_id']}\t{step['status']}\t{step['expected_output']}")
    elif args.cmd == "mark-completed":
        print(mark_completed(args.workspace, args.step_id))
    elif args.cmd == "reset-step":
        print(reset_step(args.workspace, args.step_id))
    elif args.cmd == "finalize":
        print(finalize_workspace(args.workspace, skill_root=ROOT))


if __name__ == "__main__":
    main()
