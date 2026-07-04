#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.agent_native import finalize_workspace


def main() -> None:
    ap = argparse.ArgumentParser(description="Finalize an agent-native review workspace without calling a model API.")
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    summary = finalize_workspace(args.workspace, skill_root=ROOT)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        status = summary.get("status", "incomplete")
        if status == "complete":
            print(f"Finalized complete workspace: {args.workspace.resolve()}")
        else:
            print(f"Finalized incomplete workspace with warnings: {args.workspace.resolve()}")
        print(f"Completed steps: {summary['completed_steps']}/{summary['total_steps']}")
        print(f"Warnings: {len(summary['warnings'])}")
        print(f"Final reports: {args.workspace.resolve() / 'final'}")


if __name__ == "__main__":
    main()
