#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.costing import write_workflow_cost_estimate
MODES = {"quick":"quick_review.yaml", "standard":"standard_review.yaml", "full":"full_review.yaml", "visual-citation":"visual_citation_review.yaml", "final-check":"final_submission_check.yaml", "diagnostic":"diagnostic_review.yaml", "privacy-preview":"privacy_preview.yaml", "revision-check":"revision_check.yaml", "research-eval":"research_eval.yaml"}

def main() -> None:
    ap = argparse.ArgumentParser(description="Estimate relative workflow size and model planning needs.")
    ap.add_argument("--packet", required=True, type=Path)
    ap.add_argument("--workflow", type=Path, default=None)
    ap.add_argument("--mode", choices=sorted(MODES), default="standard")
    ap.add_argument("--out", type=Path, default=Path("cost_estimate"))
    ap.add_argument("--images-enabled", action="store_true", default=False)
    args = ap.parse_args()
    workflow = args.workflow or ROOT / "workflow" / MODES[args.mode]
    report = write_workflow_cost_estimate(args.packet, workflow, args.out, images_enabled=args.images_enabled or os.environ.get("AI_REVIEWER_SEND_IMAGES") == "1")
    print(f"step_count={report['step_count']} base_context_chars={report['base_context_chars']}")
if __name__ == "__main__":
    main()
