#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.agent_native import MODE_TO_WORKFLOW, create_workspace


def main() -> None:
    ap = argparse.ArgumentParser(description="Prepare an agent-native review workspace without calling any model API.")
    ap.add_argument("--input", required=True, type=Path, help="Manuscript folder or a single manuscript file.")
    ap.add_argument("--workspace", required=True, type=Path, help="Agent review workspace to create.")
    ap.add_argument("--mode", default="standard", choices=sorted(MODE_TO_WORKFLOW), help="Workflow mode to use.")
    ap.add_argument("--venue", default="")
    ap.add_argument("--field", default="")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite an existing workspace.")
    ap.add_argument("--pdf-text", default="auto", choices=["auto", "off", "force"])
    ap.add_argument("--pdf-visuals", default="auto", choices=["auto", "off", "force"])
    ap.add_argument("--pdf-engine", default="simple", choices=["simple", "off", "auto", "docling", "marker", "grobid"])
    ap.add_argument("--grobid-endpoint", default="http://localhost:8070")
    args = ap.parse_args()
    state = create_workspace(
        input_path=args.input,
        workspace=args.workspace,
        mode=args.mode,
        skill_root=ROOT,
        overwrite=args.overwrite,
        venue=args.venue,
        field=args.field,
        pdf_text=args.pdf_text,
        pdf_visuals=args.pdf_visuals,
        pdf_engine=args.pdf_engine,
        grobid_endpoint=args.grobid_endpoint,
    )
    print(f"Created agent-native review workspace: {args.workspace.resolve()}")
    print(f"Review packet: {args.workspace.resolve() / state['packet_path']}")
    print(f"Mode: {state['mode']}")
    print(f"Steps: {len(state['steps'])}")
    print(f"Next step file: {args.workspace.resolve() / 'NEXT_STEP.md'}")


if __name__ == "__main__":
    main()
