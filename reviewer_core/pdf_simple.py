from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any


def _normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _section_slug(title: str, fallback: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_")
    return text[:70] or fallback


def _looks_like_heading(line: str) -> bool:
    clean = line.strip()
    if not clean or len(clean) > 120:
        return False
    lower = clean.lower().rstrip(":")
    common = {
        "abstract", "introduction", "background", "related work", "methods", "method", "materials and methods",
        "experiments", "experimental setup", "results", "discussion", "limitations", "conclusion",
        "conclusions", "references", "acknowledgements", "acknowledgments", "appendix",
    }
    if lower in common:
        return True
    if re.match(r"^(\d+|[IVX]+)\.?\s+[A-Z][A-Za-z0-9 ,:;()\-/]{2,}$", clean):
        return True
    if clean.isupper() and 4 <= len(clean) <= 80 and any(ch.isalpha() for ch in clean):
        return True
    return False


def _looks_like_caption(line: str) -> bool:
    return bool(re.match(r"^(fig\.?|figure|table)\s*[0-9IVXivx]+[.:\s-]", line.strip(), flags=re.I))


def _quality_label(*, status: str, page_count: int, total_lines: int, total_chars: int, section_count: int) -> str:
    if status != "ok":
        return "failed"
    if page_count == 0 or total_chars < 500 or total_lines < 20:
        return "weak"
    if section_count == 0 or total_chars < 3000:
        return "usable"
    return "good"


def _visual_quality_label(*, status: str, page_image_count: int, embedded_image_count: int, page_count: int) -> str:
    if status != "ok":
        return "failed"
    if page_image_count == 0 and embedded_image_count == 0:
        return "weak"
    if page_image_count < min(page_count, 3):
        return "usable"
    return "good"




def _extract_citation_markers(line: str, anchor: str) -> list[dict[str, Any]]:
    """Return lightweight citation marker candidates from extracted PDF text."""
    markers: list[dict[str, Any]] = []
    # Numeric forms: [1], [1, 2], [1-3]
    for m in re.finditer(r"\[(\d+(?:\s*[-,;]\s*\d+)*)\]", line):
        markers.append({"type": "numeric", "marker": m.group(0), "value": m.group(1), "anchor": anchor})
    # Author-year parentheticals: (Smith, 2020), (Smith et al., 2020; Jones, 2021)
    for m in re.finditer(r"\(([A-Z][A-Za-z'`-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?(?:\s*;\s*[A-Z][A-Za-z'`-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?){0,5})\)", line):
        markers.append({"type": "author_year", "marker": m.group(0), "value": m.group(1), "anchor": anchor})
    # Textual forms: Smith et al. (2020)
    for m in re.finditer(r"\b([A-Z][A-Za-z'`-]+\s+et\s+al\.)\s*\((\d{4}[a-z]?)\)", line):
        markers.append({"type": "textual_author_year", "marker": m.group(0), "value": f"{m.group(1)} {m.group(2)}", "anchor": anchor})
    return markers


def _is_references_heading(line: str) -> bool:
    lower = line.strip().lower().rstrip(':')
    return lower in {"references", "bibliography", "works cited", "literature cited"}


def _reference_start(line: str) -> re.Match[str] | None:
    clean = line.strip()
    patterns = [
        r"^\[(\d{1,4})\]\s+(.+)",
        r"^(\d{1,4})\.\s+(.+)",
        r"^([A-Z][A-Za-z'`-]+,\s+[A-Z].+\d{4}.+)",
    ]
    for pattern in patterns:
        m = re.match(pattern, clean)
        if m:
            return m
    return None


def _build_reference_entries(reference_lines: list[dict[str, str]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for item in reference_lines:
        text = item["text"]
        start = _reference_start(text)
        if start:
            if current:
                current["text"] = re.sub(r"\s+", " ", current["text"]).strip()
                entries.append(current)
            label = start.group(1) if start.lastindex else ""
            current = {"label": label, "start_anchor": item["anchor"], "text": text}
        elif current:
            current["text"] += " " + text
        elif len(text) > 20:
            current = {"label": "", "start_anchor": item["anchor"], "text": text}
    if current:
        current["text"] = re.sub(r"\s+", " ", current["text"]).strip()
        entries.append(current)
    return entries[:500]


def _write_citation_reference_index(out_root: Path, citation_manifest: dict[str, Any]) -> None:
    lines = [
        "# Citation and Reference Candidate Index",
        "",
        "This is a lightweight PDF-derived aid for citation auditing. It is approximate and should be checked against the source files or bibliography when available.",
        "",
        f"Citation markers: `{citation_manifest.get('citation_marker_count', 0)}`",
        f"Reference entries: `{citation_manifest.get('reference_entry_count', 0)}`",
        f"Unresolved numeric citations: `{len(citation_manifest.get('unresolved_numeric_citations', []))}`",
        f"Possibly uncited numeric references: `{len(citation_manifest.get('possibly_uncited_numeric_references', []))}`",
        "",
    ]
    if citation_manifest.get("unresolved_numeric_citations"):
        lines.extend(["## Unresolved numeric citation markers", "", "| Marker | Anchors |", "|---|---|"])
        for item in citation_manifest.get("unresolved_numeric_citations", [])[:100]:
            lines.append(f"| `{item.get('number')}` | {', '.join('`'+a+'`' for a in item.get('anchors', [])[:5])} |")
        lines.append("")
    if citation_manifest.get("reference_entries"):
        lines.extend(["## Reference entry candidates", "", "| Label | Anchor | Text preview |", "|---|---|---|"])
        for entry in citation_manifest.get("reference_entries", [])[:100]:
            preview = str(entry.get("text", ""))[:220].replace("|", "\\|")
            lines.append(f"| `{entry.get('label', '')}` | `{entry.get('start_anchor', '')}` | {preview} |")
        lines.append("")
    lines.extend([
        "## Reviewer guidance",
        "",
        "- Treat these as candidates, not ground truth.",
        "- Prefer BibTeX or source-file citation anchors when available.",
        "- Use this index to find citation-density gaps, uncited references, and unsupported novelty claims.",
    ])
    (out_root / "citation_reference_index.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_visual_index(out_root: Path, visual_manifest: dict[str, Any]) -> None:
    lines = [
        "# PDF Visual Asset Index",
        "",
        "This file lists visual assets extracted from the PDF for visual/figure review.",
        "Page render images are the safest lightweight representation for figures, tables, equations, and layout because they preserve the original PDF view.",
        "",
        f"Visual extraction quality: `{visual_manifest.get('visual_extraction_quality', 'unknown')}`",
        f"Page images: `{visual_manifest.get('page_image_count', 0)}`",
        f"Embedded images: `{visual_manifest.get('embedded_image_count', 0)}`",
        "",
    ]
    if visual_manifest.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for warning in visual_manifest.get("warnings", []):
            lines.append(f"- {warning}")
        lines.append("")
    if visual_manifest.get("page_images"):
        lines.extend(["## Page render images", "", "| Page | Anchor | File | Size |", "|---:|---|---|---:|"])
        for item in visual_manifest.get("page_images", []):
            lines.append(f"| {item.get('page')} | `{item.get('anchor')}` | `{item.get('file')}` | {item.get('bytes', 0)} |")
        lines.append("")
    if visual_manifest.get("embedded_images"):
        lines.extend(["## Embedded images", "", "| Page | XRef | File | Ext | Size |", "|---:|---:|---|---|---:|"])
        for item in visual_manifest.get("embedded_images", []):
            lines.append(f"| {item.get('page')} | {item.get('xref')} | `{item.get('file')}` | {item.get('ext')} | {item.get('bytes', 0)} |")
        lines.append("")
    if visual_manifest.get("caption_candidates"):
        lines.extend(["## Caption candidates", "", "| Anchor | Text |", "|---|---|"])
        for cap in visual_manifest.get("caption_candidates", []):
            safe_text = str(cap.get("text", "")).replace("|", "\\|")
            lines.append(f"| `{cap.get('anchor')}` | {safe_text} |")
        lines.append("")
    lines.extend([
        "## Reviewer guidance",
        "",
        "- Use page images to inspect figure/table readability, axis labels, legends, flow diagrams, equations, and visual evidence.",
        "- Use extracted text anchors for claims and page images for visual corroboration.",
        "- If a model cannot receive images, upload selected page images manually or run only the text-based workflow.",
    ])
    (out_root / "visual_index.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _get_text_sorted(page) -> str:
    """Extract page text in natural reading order (helps multi-column layouts)."""
    try:
        return page.get_text("text", sort=True) or ""
    except TypeError:  # older PyMuPDF without the sort keyword
        return page.get_text("text") or ""


def _extract_document_metadata(doc) -> dict[str, Any]:
    """Pull lightweight document metadata (title/author/subject/keywords)."""
    meta: dict[str, Any] = {}
    try:
        raw = doc.metadata or {}
    except Exception:
        return meta
    for key in ("title", "author", "subject", "keywords"):
        value = raw.get(key)
        if value:
            meta[key] = str(value)[:500]
    return meta


def _extract_pdf_tables(doc, pdf_name: str, out_root: Path, *, max_tables: int = 100) -> dict[str, Any]:
    """Detect tables with PyMuPDF's table finder and emit anchored Markdown.

    This is a real structured-table improvement over plain text flow. It is bounded
    and fully guarded: any per-page/table failure is skipped rather than fatal, and a
    PyMuPDF build without ``find_tables`` yields zero tables.
    """
    tables: list[dict[str, Any]] = []
    md_lines = [
        f"# Extracted PDF Tables: {pdf_name}",
        "",
        "Detected with PyMuPDF's table finder. Structure is approximate; verify against "
        "the page render images or the source when precision matters.",
        "",
    ]
    count = 0
    for page_index, page in enumerate(doc, start=1):
        if count >= max_tables:
            break
        try:
            finder = page.find_tables()
            found = list(getattr(finder, "tables", []) or [])
        except Exception:
            continue
        for t_index, table in enumerate(found, start=1):
            if count >= max_tables:
                break
            try:
                markdown = table.to_markdown()
            except Exception:
                continue
            if not markdown or not markdown.strip():
                continue
            count += 1
            anchor = f"{pdf_name}:p{page_index}:table{t_index}"
            tables.append({
                "page": page_index,
                "index": t_index,
                "anchor": anchor,
                "rows": getattr(table, "row_count", None),
                "cols": getattr(table, "col_count", None),
            })
            md_lines.extend([
                f"## Table {count} (page {page_index})",
                "",
                f"Anchor: `{anchor}`",
                "",
                markdown.strip(),
                "",
            ])
    report: dict[str, Any] = {"table_count": count, "tables": tables, "file": None}
    if count:
        (out_root / "pdf_tables.md").write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
        report["file"] = "pdf_tables.md"
    return report


def extract_pdf_to_markdown(
    pdf_path: Path,
    out_root: Path,
    *,
    extract_visuals: bool = True,
    render_dpi: int = 120,
    max_render_pages: int = 30,
    max_embedded_images: int = 200,
) -> dict[str, Any]:
    """Extract a scholarly PDF into review-friendly text and optional visual assets.

    This intentionally uses one lightweight dependency path: PyMuPDF. It does not
    attempt full LaTeX reconstruction, complex layout semantics, or OCR. Instead
    it provides:
    - page/line anchored Markdown text;
    - page render PNGs for figure/table/equation/layout inspection;
    - embedded raster images when available;
    - a visual manifest that can be consumed by a vision-capable reviewer step.
    """
    pdf_path = Path(pdf_path).resolve()
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "source_pdf": pdf_path.name,
        "method": "pymupdf-simple-text-plus-visuals" if extract_visuals else "pymupdf-simple-text",
        "status": "not_run",
        "extraction_quality": "failed",
        "visual_extraction_quality": "not_requested" if not extract_visuals else "failed",
        "pages": [],
        "sections": [],
        "caption_candidates": [],
        "visual_assets": None,
        "warnings": [],
    }
    try:
        import fitz  # type: ignore
    except Exception:
        manifest["status"] = "missing_dependency"
        manifest["warnings"].append("PyMuPDF is not installed. Install optional dependency: pip install pymupdf")
        (out_root / "pdf_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["warnings"].append(f"Could not open PDF: {exc}")
        (out_root / "pdf_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    page_md_lines: list[str] = [
        f"# Extracted PDF Text: {pdf_path.name}",
        "",
        "Extraction method: simple PDF text extraction with page/line anchors.",
        "Use these anchors for evidence-grounded review. Visual assets, when extracted, are listed in `visual_index.md`.",
        "",
    ]
    section_chunks: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    total_lines = 0
    total_chars = 0
    caption_candidates: list[dict[str, Any]] = []
    citation_markers: list[dict[str, Any]] = []
    reference_lines: list[dict[str, str]] = []
    in_references = False

    for page_index, page in enumerate(doc, start=1):
        raw = _get_text_sorted(page)
        lines = [_normalise_line(line) for line in raw.splitlines()]
        lines = [line for line in lines if line]
        total_lines += len(lines)
        total_chars += sum(len(line) for line in lines)
        page_anchor = f"{pdf_path.name}:p{page_index}"
        page_md_lines.extend([f"## Page {page_index}", "", f"Anchor: `{page_anchor}`", "", "```text"])
        for line_index, line in enumerate(lines, start=1):
            anchor = f"{pdf_path.name}:p{page_index}:L{line_index}"
            page_md_lines.append(f"P{page_index}L{line_index}: {line}")
            citation_markers.extend(_extract_citation_markers(line, anchor))
            if _is_references_heading(line):
                in_references = True
            elif in_references:
                reference_lines.append({"anchor": anchor, "text": line})
            if _looks_like_caption(line):
                caption_candidates.append({"anchor": anchor, "text": line})
            if _looks_like_heading(line):
                if current_section and current_section.get("lines"):
                    section_chunks.append(current_section)
                current_section = {
                    "title": line,
                    "start_anchor": anchor,
                    "lines": [f"{anchor}: {line}"],
                }
            elif current_section is not None:
                current_section["lines"].append(f"{anchor}: {line}")
        page_md_lines.extend(["```", ""])
        manifest["pages"].append({"page": page_index, "anchor": page_anchor, "line_count": len(lines)})

    if current_section and current_section.get("lines"):
        section_chunks.append(current_section)

    (out_root / "extracted_pdf.md").write_text("\n".join(page_md_lines).rstrip() + "\n", encoding="utf-8")

    sections_dir = out_root / "pdf_sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    for idx, section in enumerate(section_chunks, start=1):
        title = str(section.get("title") or f"Section {idx}")
        fname = f"{idx:02d}_{_section_slug(title, f'section_{idx}')}.md"
        body = [f"# {title}", "", f"Start anchor: `{section.get('start_anchor')}`", "", "```text"]
        body.extend(section.get("lines", []))
        body.append("```")
        (sections_dir / fname).write_text("\n".join(body) + "\n", encoding="utf-8")
        manifest["sections"].append({"title": title, "file": f"pdf_sections/{fname}", "start_anchor": section.get("start_anchor")})

    if not manifest["sections"]:
        manifest["warnings"].append("No clear section headings detected; reviewers should cite page/line anchors instead.")

    # Lightweight document metadata (title/author/keywords) aids paper-map and
    # prior-work steps; structured tables recover content the flat text flow garbles.
    manifest["document_metadata"] = _extract_document_metadata(doc)
    try:
        table_report = _extract_pdf_tables(doc, pdf_path.name, out_root)
    except Exception as exc:
        table_report = {"table_count": 0, "tables": [], "file": None, "error": str(exc)}
    manifest["table_assets"] = table_report
    if table_report.get("table_count"):
        manifest["warnings"].append(
            f"Detected {table_report['table_count']} table(s) via the PDF table finder "
            "(`derived/pdf/pdf_tables.md`); structure is approximate, verify against page images."
        )

    manifest["caption_candidates"] = caption_candidates[:200]
    reference_entries = _build_reference_entries(reference_lines)
    numeric_citations: dict[str, list[str]] = {}
    for marker in citation_markers:
        if marker.get("type") == "numeric":
            for number in re.findall(r"\d+", str(marker.get("value", ""))):
                numeric_citations.setdefault(number, []).append(str(marker.get("anchor")))
    numeric_refs = {str(entry.get("label")) for entry in reference_entries if str(entry.get("label", "")).isdigit()}
    unresolved_numeric = [
        {"number": number, "anchors": anchors[:20]}
        for number, anchors in sorted(numeric_citations.items(), key=lambda x: int(x[0]))
        if number not in numeric_refs
    ]
    possibly_uncited = sorted([number for number in numeric_refs if number not in numeric_citations], key=lambda x: int(x))
    citation_reference_manifest = {
        "source_pdf": pdf_path.name,
        "method": "pymupdf-lightweight-citation-reference-candidates",
        "status": "ok",
        "citation_markers": citation_markers[:1000],
        "citation_marker_count": len(citation_markers),
        "reference_entries": reference_entries,
        "reference_entry_count": len(reference_entries),
        "numeric_citation_numbers": sorted(numeric_citations.keys(), key=lambda x: int(x)),
        "numeric_reference_numbers": sorted(numeric_refs, key=lambda x: int(x)) if numeric_refs else [],
        "unresolved_numeric_citations": unresolved_numeric[:200],
        "possibly_uncited_numeric_references": possibly_uncited[:200],
        "warnings": [
            "PDF citation/reference extraction is approximate. Prefer BibTeX/source files for authoritative citation audit."
        ],
    }
    (out_root / "citation_reference_manifest.json").write_text(json.dumps(citation_reference_manifest, indent=2), encoding="utf-8")
    _write_citation_reference_index(out_root, citation_reference_manifest)
    manifest["citation_reference_assets"] = {
        "citation_reference_manifest": "citation_reference_manifest.json",
        "citation_reference_index": "citation_reference_index.md",
        "citation_marker_count": len(citation_markers),
        "reference_entry_count": len(reference_entries),
        "unresolved_numeric_citation_count": len(unresolved_numeric),
        "possibly_uncited_numeric_reference_count": len(possibly_uncited),
    }
    manifest["status"] = "ok"
    manifest["page_count"] = len(manifest["pages"])
    manifest["section_count"] = len(manifest["sections"])
    manifest["total_line_count"] = total_lines
    manifest["total_text_chars"] = total_chars
    manifest["extraction_quality"] = _quality_label(
        status="ok",
        page_count=manifest["page_count"],
        total_lines=total_lines,
        total_chars=total_chars,
        section_count=manifest["section_count"],
    )
    if manifest["extraction_quality"] in {"weak", "usable"}:
        manifest["warnings"].append(
            f"Extraction quality is {manifest['extraction_quality']}; prefer LaTeX, Markdown, or manually cleaned section text when available."
        )
    # Scanned / image-only PDFs yield little or no extractable text. Surface this
    # explicitly so the reviewer does not silently proceed on an empty manuscript.
    if manifest["page_count"] > 0 and (
        total_chars < 100 or (total_chars / max(manifest["page_count"], 1)) < 40
    ):
        manifest["likely_scanned"] = True
        manifest["warnings"].append(
            "This PDF appears to be scanned or image-only: little or no selectable text was "
            "extracted. Provide a text-based source (LaTeX/Markdown/DOCX) or an OCR'd PDF; the "
            "page render images can still be used for visual review."
        )

    if extract_visuals:
        visual_manifest: dict[str, Any] = {
            "source_pdf": pdf_path.name,
            "method": "pymupdf-page-renders-and-embedded-images",
            "status": "ok",
            "render_dpi": render_dpi,
            "max_render_pages": max_render_pages,
            "max_embedded_images": max_embedded_images,
            "page_images": [],
            "embedded_images": [],
            "caption_candidates": caption_candidates[:200],
            "warnings": [],
        }
        page_img_dir = out_root / "page_images"
        embedded_img_dir = out_root / "embedded_images"
        page_img_dir.mkdir(parents=True, exist_ok=True)
        embedded_img_dir.mkdir(parents=True, exist_ok=True)

        matrix = fitz.Matrix(render_dpi / 72, render_dpi / 72)
        render_limit = max(0, min(max_render_pages, len(doc)))
        for page_index in range(render_limit):
            page = doc[page_index]
            try:
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                fname = f"page_{page_index + 1:03d}.png"
                target = page_img_dir / fname
                pix.save(str(target))
                visual_manifest["page_images"].append({
                    "page": page_index + 1,
                    "anchor": f"{pdf_path.name}:p{page_index + 1}",
                    "file": f"page_images/{fname}",
                    "width": pix.width,
                    "height": pix.height,
                    "bytes": target.stat().st_size,
                })
            except Exception as exc:
                visual_manifest["warnings"].append(f"Could not render page {page_index + 1}: {exc}")
        if len(doc) > render_limit:
            visual_manifest["warnings"].append(
                f"Rendered first {render_limit} of {len(doc)} pages to keep the packet lightweight. Increase --max-render-pages if needed."
            )

        seen_xrefs: set[int] = set()
        embedded_count = 0
        for page_index, page in enumerate(doc, start=1):
            if embedded_count >= max_embedded_images:
                break
            try:
                images = page.get_images(full=True)
            except Exception:
                images = []
            for image_pos, image in enumerate(images, start=1):
                if embedded_count >= max_embedded_images:
                    break
                xref = int(image[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    info = doc.extract_image(xref)
                    data = info.get("image")
                    if not data:
                        continue
                    ext = re.sub(r"[^a-zA-Z0-9]+", "", str(info.get("ext") or "bin"))[:10] or "bin"
                    fname = f"p{page_index:03d}_xref{xref}_{image_pos:03d}.{ext}"
                    target = embedded_img_dir / fname
                    target.write_bytes(data)
                    embedded_count += 1
                    visual_manifest["embedded_images"].append({
                        "page": page_index,
                        "xref": xref,
                        "file": f"embedded_images/{fname}",
                        "ext": ext,
                        "width": info.get("width"),
                        "height": info.get("height"),
                        "bytes": target.stat().st_size,
                    })
                except Exception as exc:
                    visual_manifest["warnings"].append(f"Could not extract embedded image xref {xref} on page {page_index}: {exc}")
        if embedded_count >= max_embedded_images:
            visual_manifest["warnings"].append(f"Stopped embedded-image extraction at max_embedded_images={max_embedded_images}.")

        visual_manifest["page_count"] = len(doc)
        visual_manifest["page_image_count"] = len(visual_manifest["page_images"])
        visual_manifest["embedded_image_count"] = len(visual_manifest["embedded_images"])
        visual_manifest["visual_extraction_quality"] = _visual_quality_label(
            status="ok",
            page_image_count=visual_manifest["page_image_count"],
            embedded_image_count=visual_manifest["embedded_image_count"],
            page_count=len(doc),
        )
        if visual_manifest["visual_extraction_quality"] in {"weak", "usable"}:
            visual_manifest["warnings"].append(
                f"Visual extraction quality is {visual_manifest['visual_extraction_quality']}; inspect the original PDF manually if visual evidence is important."
            )
        (out_root / "visual_manifest.json").write_text(json.dumps(visual_manifest, indent=2), encoding="utf-8")
        _write_visual_index(out_root, visual_manifest)
        manifest["visual_assets"] = {
            "visual_manifest": "visual_manifest.json",
            "visual_index": "visual_index.md",
            "page_image_count": visual_manifest["page_image_count"],
            "embedded_image_count": visual_manifest["embedded_image_count"],
            "visual_extraction_quality": visual_manifest["visual_extraction_quality"],
        }
        manifest["visual_extraction_quality"] = visual_manifest["visual_extraction_quality"]
    else:
        manifest["warnings"].append("PDF visual asset extraction was disabled.")

    (out_root / "pdf_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
