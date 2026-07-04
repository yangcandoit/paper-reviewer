#!/usr/bin/env python3
r"""Build a structured review packet from a manuscript folder.

Features:
- Copies source files into a stable packet layout.
- Resolves simple LaTeX \input / \include chains.
- Generates line-anchored derived section files.
- Extracts figure/table/equation/citation anchors from LaTeX.
- Uses one simple optional PDF text/visual extraction path for page-grounded review.
- Parses BibTeX entries into JSON.
- Writes manifest.json and REVIEW_PACKET_INDEX.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.packet import build_packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a manuscript review packet.")
    parser.add_argument("--input", required=True, help="Input folder containing manuscript files.")
    parser.add_argument("--output", required=True, help="Output review packet folder.")
    parser.add_argument("--venue", default="", help="Target venue or journal.")
    parser.add_argument("--field", default="", help="Research field/domain.")
    parser.add_argument("--mode", default="standard", choices=["fast", "standard", "full", "final-check", "audit-only"], help="Suggested review mode.")
    parser.add_argument("--pdf-text", default="auto", choices=["auto", "off", "force"], help="Simple PDF text extraction: auto extracts the first PDF when present; off disables it.")
    parser.add_argument("--pdf-visuals", default="auto", choices=["auto", "off", "force"], help="Render PDF pages and extract embedded images for visual review: auto when PDF is present; off disables it.")
    parser.add_argument("--pdf-engine", default="simple", choices=["simple", "off", "auto", "docling", "marker", "grobid"], help="Optional advanced PDF ingestion engine. Use auto to select an available local advanced engine; default simple keeps dependencies light.")
    parser.add_argument("--grobid-endpoint", default="http://localhost:8070", help="Local GROBID endpoint for --pdf-engine grobid; localhost only.")
    parser.add_argument("--render-dpi", type=int, default=120, help="DPI for PDF page render images.")
    parser.add_argument("--max-render-pages", type=int, default=30, help="Maximum PDF pages to render as images.")
    parser.add_argument("--max-embedded-images", type=int, default=200, help="Maximum embedded raster images to extract from a PDF.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output folder if it exists.")
    args = parser.parse_args()

    manifest = build_packet(
        Path(args.input),
        Path(args.output),
        venue=args.venue,
        field=args.field,
        mode=args.mode,
        overwrite=args.overwrite,
        pdf_text=args.pdf_text,
        pdf_visuals=args.pdf_visuals,
        pdf_engine=args.pdf_engine,
        grobid_endpoint=args.grobid_endpoint,
        render_dpi=args.render_dpi,
        max_render_pages=args.max_render_pages,
        max_embedded_images=args.max_embedded_images,
    )
    print(f"Created review packet: {Path(args.output).resolve()}")
    print(f"Files copied: {len(manifest.get('files', []))}")
    print(f"BibTeX entries: {manifest.get('bibtex_entry_count', 0)}")
    if manifest.get("latex_manifest"):
        print(f"Derived LaTeX sections: {len(manifest['latex_manifest'].get('sections', []))}")
    if manifest.get("pdf_manifest"):
        print(f"PDF extraction status: {manifest['pdf_manifest'].get('status')}")
        print(f"PDF extraction quality: {manifest['pdf_manifest'].get('extraction_quality', 'unknown')}")
        print(f"Derived PDF sections: {manifest['pdf_manifest'].get('section_count', 0)}")
        visuals = manifest['pdf_manifest'].get('visual_assets') or {}
        if visuals:
            print(f"PDF visual quality: {visuals.get('visual_extraction_quality', 'unknown')}")
            print(f"Page render images: {visuals.get('page_image_count', 0)}")
            print(f"Embedded images: {visuals.get('embedded_image_count', 0)}")
        cr = manifest['pdf_manifest'].get('citation_reference_assets') or {}
        if cr:
            print(f"PDF citation markers: {cr.get('citation_marker_count', 0)}")
            print(f"PDF reference entries: {cr.get('reference_entry_count', 0)}")
    if manifest.get("advanced_pdf_manifest"):
        adv = manifest["advanced_pdf_manifest"]
        print(f"Advanced PDF engine: {adv.get('engine')}")
        print(f"Advanced PDF status: {adv.get('status')}")
    if manifest.get("coverage_status"):
        print(f"Coverage status: {manifest.get('coverage_status')}")


if __name__ == "__main__":
    main()
