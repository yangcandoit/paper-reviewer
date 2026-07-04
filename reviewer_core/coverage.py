from __future__ import annotations

from pathlib import Path
import json
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _count_files(path: Path, patterns: list[str]) -> int:
    total = 0
    for pattern in patterns:
        total += len([p for p in path.glob(pattern) if p.is_file()])
    return total


def audit_review_packet(packet_dir: Path, *, write_files: bool = True) -> dict[str, Any]:
    """Create a deterministic coverage report for a manuscript review packet.

    This is intentionally lightweight. It does not judge scientific quality; it
    checks whether the packet contains enough material for the LLM reviewers to
    inspect the full manuscript: text, sections, PDF anchors, visuals, captions,
    citations, references, prior-work queries, tables, and supplemental files.
    """
    packet_dir = Path(packet_dir).resolve()
    manifest = _load_json(packet_dir / "manifest.json")
    pdf_manifest = _load_json(packet_dir / "derived" / "pdf" / "pdf_extraction_manifest.json")
    visual_manifest = _load_json(packet_dir / "derived" / "pdf" / "visual_manifest.json")
    citation_manifest = _load_json(packet_dir / "derived" / "pdf" / "citation_reference_manifest.json")
    docx_manifest = _load_json(packet_dir / "derived" / "docx" / "docx_extraction_manifest.json")
    doc_manifest = _load_json(packet_dir / "derived" / "doc" / "doc_extraction_manifest.json")
    bib_manifest = _load_json(packet_dir / "references" / "bibtex_entries.json")
    query_plan = _load_json(packet_dir / "prior_work" / "query_plan.json")

    files = manifest.get("files", []) if isinstance(manifest.get("files"), list) else []
    categories = {str(item.get("category", "")) for item in files if isinstance(item, dict)}
    latex_sections = len(((manifest.get("latex_manifest") or {}).get("sections") or []))
    pdf_sections = len(pdf_manifest.get("sections") or [])
    docx_paragraphs = int(docx_manifest.get("paragraph_count") or 0) if docx_manifest.get("status") == "ok" else 0
    doc_paragraphs = int(doc_manifest.get("paragraph_count") or 0) if doc_manifest.get("status") == "ok" else 0
    pdf_pages = int(pdf_manifest.get("page_count") or 0)
    page_images = int(visual_manifest.get("page_image_count") or 0)
    embedded_images = int(visual_manifest.get("embedded_image_count") or 0)
    docx_images = int(docx_manifest.get("image_count") or 0) if docx_manifest.get("status") == "ok" else 0
    captions = len(pdf_manifest.get("caption_candidates") or []) + len(((manifest.get("asset_manifest") or {}).get("assets") or []))
    citations = len(((manifest.get("asset_manifest") or {}).get("citations") or [])) + int(citation_manifest.get("citation_marker_count") or 0)
    bib_entries = int(manifest.get("bibtex_entry_count") or len(bib_manifest.get("entries") or []))
    pdf_reference_entries = int(citation_manifest.get("reference_entry_count") or 0)
    prior_queries = int(manifest.get("prior_work_query_count") or len(query_plan.get("queries") or []))

    dimensions = [
        {
            "dimension": "manuscript_text",
            "status": "covered" if latex_sections or pdf_sections or docx_paragraphs or doc_paragraphs or _count_files(packet_dir, ["sections/**/*.md", "sections/**/*.txt", "sections/**/*.tex"]) else "missing",
            "evidence": f"latex_sections={latex_sections}; pdf_sections={pdf_sections}; docx_paragraphs={docx_paragraphs}; doc_paragraphs={doc_paragraphs}",
            "risk_if_missing": "The reviewers may only see file names or partial context.",
            "recommended_action": "Provide LaTeX/Markdown/text/Word, or enable PDF text extraction.",
        },
        {
            "dimension": "pdf_page_anchors",
            "status": "covered" if pdf_pages else "missing_or_not_applicable",
            "evidence": f"pdf_pages={pdf_pages}; quality={pdf_manifest.get('extraction_quality', 'unknown')}",
            "risk_if_missing": "P0/P1 issues may lack page-grounded evidence anchors.",
            "recommended_action": "Include the PDF and run build_review_packet with --pdf-text auto.",
        },
        {
            "dimension": "visual_figures_tables_equations",
            "status": "covered" if page_images or embedded_images or docx_images else "missing_or_not_applicable",
            "evidence": f"page_images={page_images}; embedded_images={embedded_images}; docx_images={docx_images}; quality={visual_manifest.get('visual_extraction_quality', 'unknown')}",
            "risk_if_missing": "The visual/figure reviewer cannot inspect plots, diagrams, equations, or layout.",
            "recommended_action": "Run with --pdf-visuals auto and, if using a vision model, opt in with AI_REVIEWER_SEND_IMAGES=1.",
        },
        {
            "dimension": "captions_and_visual_links",
            "status": "covered" if captions else "weak_or_missing",
            "evidence": f"caption_candidates_and_tex_assets={captions}",
            "risk_if_missing": "Figure/table claims may be hard to connect to visual evidence.",
            "recommended_action": "Provide source files or inspect derived/pdf/visual_index.md manually.",
        },
        {
            "dimension": "citations_in_text",
            "status": "covered" if citations else "weak_or_missing",
            "evidence": f"citation_markers={citations}",
            "risk_if_missing": "Citation auditor may miss unsupported prior-work claims.",
            "recommended_action": "Provide LaTeX/BibTeX when possible; otherwise use the PDF citation candidates as an approximate audit input.",
        },
        {
            "dimension": "reference_list",
            "status": "covered" if bib_entries or pdf_reference_entries else "weak_or_missing",
            "evidence": f"bibtex_entries={bib_entries}; pdf_reference_entries={pdf_reference_entries}",
            "risk_if_missing": "The reviewer cannot check whether cited work is present or whether the bibliography is adequate.",
            "recommended_action": "Provide a .bib file or ensure the PDF reference section is extractable.",
        },
        {
            "dimension": "prior_work_search_plan",
            "status": "covered" if prior_queries else "weak_or_missing",
            "evidence": f"query_count={prior_queries}",
            "risk_if_missing": "Novelty review will rely only on supplied text and may require external verification.",
            "recommended_action": "Use scripts/generate_prior_work_queries.py and optionally scripts/search_prior_work.py.",
        },
        {
            "dimension": "tables_or_data_files",
            "status": "covered" if "tables" in categories or _count_files(packet_dir, ["tables/*"]) else "missing_or_not_applicable",
            "evidence": f"table_files={_count_files(packet_dir, ['tables/*'])}",
            "risk_if_missing": "Numeric evidence may only be visible through the PDF/page renders.",
            "recommended_action": "Provide CSV/TSV/XLSX tables when available, or ensure the PDF page images are rendered.",
        },
        {
            "dimension": "supplementary_material",
            "status": "covered" if _count_files(packet_dir, ["source_documents/*", "misc/*"]) > 1 else "missing_or_not_applicable",
            "evidence": f"source_or_misc_files={_count_files(packet_dir, ['source_documents/*', 'misc/*'])}",
            "risk_if_missing": "Supplement-only method details, appendices, or data descriptions may be missed.",
            "recommended_action": "Include supplementary PDFs, appendices, code availability statements, and data files if relevant.",
        },
    ]

    missing_or_weak = [d for d in dimensions if str(d.get("status", "")).startswith("weak") or str(d.get("status", "")).startswith("missing")]
    report = {
        "version": "v1",
        "packet": packet_dir.name,
        "overall_status": "ready_for_full_review" if len(missing_or_weak) <= 2 else "review_with_caution",
        "dimensions": dimensions,
        "missing_or_weak_count": len(missing_or_weak),
        "notes": [
            "This audit checks coverage of review materials, not scientific quality.",
            "A missing_or_not_applicable status can be acceptable when the manuscript genuinely lacks that element.",
            "For a comprehensive review, include PDF text, page images, references, and prior-work candidates whenever possible.",
        ],
    }

    if write_files:
        cov_dir = packet_dir / "coverage"
        cov_dir.mkdir(parents=True, exist_ok=True)
        (cov_dir / "coverage_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# Review Packet Coverage Report", "", f"Overall status: `{report['overall_status']}`", "", "| Dimension | Status | Evidence | Recommended action |", "|---|---|---|---|"]
        for d in dimensions:
            evidence = str(d['evidence']).replace('|', '\\|')
            recommended_action = str(d['recommended_action']).replace('|', '\\|')
            lines.append(
                f"| {d['dimension']} | `{d['status']}` | {evidence} | {recommended_action} |"
            )
        lines.extend(["", "## Notes", ""])
        for note in report["notes"]:
            lines.append(f"- {note}")
        (cov_dir / "coverage_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
