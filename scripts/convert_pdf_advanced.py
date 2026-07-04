#!/usr/bin/env python3
"""Optional advanced PDF ingestion wrapper.

This script is an **agent-orchestrated tool**: the host agent (Codex / Claude Code)
calls it when the locally-extracted text is insufficient for tables, equations,
multi-column layout, or scanned pages. It does NOT run automatically during
``build_packet``; the agent decides whether to invoke it.

Usage (the agent runs one of these)::

    python scripts/convert_pdf_advanced.py paper.pdf \\
        --engine marker \\
        --output review_packet/derived/pdf_advanced

    python scripts/convert_pdf_advanced.py paper.pdf \\
        --engine docling \\
        --output review_packet/derived/pdf_advanced

    python scripts/convert_pdf_advanced.py paper.pdf \\
        --engine auto \\
        --output review_packet/derived/pdf_advanced

``--engine auto`` tries marker first (best LLM-ready Markdown), then docling,
then localhost GROBID (if reachable). If nothing is installed the script exits
non-zero with a clear message.

After the command succeeds the agent should read the structured Markdown / JSON
under the output directory and cite anchors from the lightweight PDF text when
reporting findings.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.advanced_ingestion import run_advanced_ingestion  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Agent-orchestrated optional advanced PDF ingestion. "
            "The host agent calls this when the lightweight PDF extraction is "
            "insufficient. Core skill functionality does not require this script."
        )
    )
    ap.add_argument("pdf", type=Path, help="Path to the PDF file to convert.")
    ap.add_argument(
        "--engine",
        choices=["docling", "marker", "grobid", "auto"],
        required=True,
        help=(
            "Conversion engine. "
            "marker: best LLM-ready Markdown output; "
            "docling: strong layout/table-oriented conversion; "
            "grobid: TEI/reference enrichment via a localhost-only GROBID service; "
            "auto: try marker → docling → localhost GROBID in that order."
        ),
    )
    ap.add_argument("--output", type=Path, required=True, help="Output directory for converted files.")
    ap.add_argument(
        "--grobid-endpoint",
        default="http://localhost:8070",
        help="Local GROBID endpoint (localhost only). Used only with --engine grobid or auto.",
    )
    args = ap.parse_args()

    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(2)

    manifest = run_advanced_ingestion(
        pdf_path,
        args.output.expanduser().resolve(),
        args.engine,
        grobid_endpoint=args.grobid_endpoint,
    )
    status = manifest.get("status", "unknown")
    engine = manifest.get("engine") or manifest.get("selected_engine", args.engine)
    outputs = manifest.get("outputs", [])
    warnings = manifest.get("warnings", [])

    print(f"engine={engine}  status={status}  outputs={len(outputs)}")
    if outputs:
        print("Output files:")
        for out in outputs[:20]:
            print(f"  {out}")
    for warning in warnings[:10]:
        print(f"WARNING: {warning}", file=sys.stderr)

    if status in {"missing_tool", "no_optional_engine_available", "rejected_endpoint", "unknown_engine"}:
        print(
            f"\nThe requested engine is unavailable ({status}). "
            "Install the engine CLI or choose a different --engine value.",
            file=sys.stderr,
        )
        sys.exit(1)

    if status == "failed":
        print(f"\nConversion failed. See warnings above.", file=sys.stderr)
        sys.exit(1)

    if status == "ok":
        print(
            f"\nConversion succeeded. Read the structured output under the output directory "
            f"and cite page/line anchors from the lightweight PDF text when reporting findings."
        )


if __name__ == "__main__":
    main()
