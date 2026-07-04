#!/usr/bin/env python3
"""Convert one PDF into simple Markdown plus optional visual assets.

This is intentionally lightweight. It uses PyMuPDF if installed and does not try
to reconstruct full LaTeX or document semantics. It can render pages and extract
embedded images so visual/figure review is possible without a heavy parser stack.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.pdf_simple import extract_pdf_to_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple PDF-to-Markdown extraction for review packets.")
    parser.add_argument("pdf", help="Input PDF file.")
    parser.add_argument("--output", required=True, help="Output folder for extracted Markdown, visual assets, and manifest.")
    parser.add_argument("--visuals", default="auto", choices=["auto", "off"], help="Render page images and extract embedded images when possible.")
    parser.add_argument("--render-dpi", type=int, default=120, help="DPI for PDF page render images.")
    parser.add_argument("--max-render-pages", type=int, default=30, help="Maximum pages to render as images.")
    parser.add_argument("--max-embedded-images", type=int, default=200, help="Maximum embedded raster images to extract.")
    args = parser.parse_args()

    manifest = extract_pdf_to_markdown(
        Path(args.pdf),
        Path(args.output),
        extract_visuals=args.visuals != "off",
        render_dpi=args.render_dpi,
        max_render_pages=args.max_render_pages,
        max_embedded_images=args.max_embedded_images,
    )
    print(f"Status: {manifest.get('status')}")
    print(f"Extraction quality: {manifest.get('extraction_quality', 'unknown')}")
    print(f"Visual quality: {manifest.get('visual_extraction_quality', 'unknown')}")
    visuals = manifest.get("visual_assets") or {}
    if visuals:
        print(f"Page images: {visuals.get('page_image_count', 0)}")
        print(f"Embedded images: {visuals.get('embedded_image_count', 0)}")
    print(f"Output: {Path(args.output).resolve()}")
    if manifest.get("warnings"):
        for warning in manifest["warnings"]:
            print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
