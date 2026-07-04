from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re
import xml.etree.ElementTree as ET

from .io_utils import TEXT_EXTS, read_text, write_json

SECTION_HEADING_RE = re.compile(r"^(?:#{1,6}\s+|L\d+:\s*)?(abstract|introduction|background|related work|methods?|approach|experiments?|evaluation|results?|discussion|limitations?|conclusions?|references|bibliography)\b", re.I)
TABLE_LINE_RE = re.compile(r"^\s*\|.+\|\s*$")
FORMULA_LINE_RE = re.compile(r"(\\begin\{(?:equation|align)|\$\$|\\\[|\\frac\{|\\sum\b|\\int\b)")
FIGURE_TABLE_RE = re.compile(r"\b(fig\.?|figure|table)\s*([0-9IVXivx]+)\b", re.I)


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return path.name


def _packet_text_files(packet: Path) -> list[Path]:
    patterns = [
        "derived/resolved_manuscript.tex",
        "derived/sections/*.md",
        "derived/pdf/pdf_sections/*.md",
        "derived/pdf/extracted_pdf.md",
        "derived/pdf_advanced/**/*.md",
        "derived/pdf_advanced/**/*.txt",
        "sections/**/*.md",
        "sections/**/*.txt",
        "sections/**/*.tex",
    ]
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in patterns:
        for path in sorted(packet.glob(pattern)):
            if path.is_file() and path not in seen and path.suffix.lower() in TEXT_EXTS.union({".tex"}):
                seen.add(path)
                files.append(path)
    return files


def _clean_line(line: str) -> str:
    line = re.sub(r"^L\d+:\s*", "", line)
    line = re.sub(r"`?[^`\s:]+\.pdf:p\d+:L\d+`?:\s*", "", line)
    return re.sub(r"\s+", " ", line).strip()


def _anchor(path: Path, packet: Path, line_no: int) -> str:
    return f"{_rel(path, packet)}:L{line_no}"


def _extract_blocks(packet: Path) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for path in _packet_text_files(packet):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            text = _clean_line(line)
            if not text:
                continue
            block_type = "paragraph"
            if SECTION_HEADING_RE.search(text):
                block_type = "heading_or_section_marker"
            elif TABLE_LINE_RE.match(line):
                block_type = "table_row"
            elif FORMULA_LINE_RE.search(line):
                block_type = "formula_or_equation"
            elif FIGURE_TABLE_RE.search(text):
                block_type = "figure_table_mention"
            blocks.append({
                "block_id": f"B{len(blocks)+1:05d}",
                "type": block_type,
                "text": text[:4000],
                "anchor": _anchor(path, packet, i),
                "source_file": _rel(path, packet),
            })
    return blocks


def _extract_sections(packet: Path, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for block in blocks:
        m = SECTION_HEADING_RE.search(block["text"])
        if m and block["type"] == "heading_or_section_marker":
            if current:
                sections.append(current)
            current = {
                "section_id": f"S{len(sections)+1:03d}",
                "title": m.group(1).lower(),
                "start_anchor": block["anchor"],
                "block_ids": [block["block_id"]],
            }
        elif current:
            current["block_ids"].append(block["block_id"])
    if current:
        sections.append(current)
    return sections


def _extract_figures(packet: Path) -> list[dict[str, Any]]:
    figures: list[dict[str, Any]] = []
    visual = _load_json(packet / "derived" / "pdf" / "visual_manifest.json")
    pdf = _load_json(packet / "derived" / "pdf" / "pdf_extraction_manifest.json")
    captions = visual.get("caption_candidates") or pdf.get("caption_candidates") or []
    for idx, cap in enumerate(captions, start=1):
        text = str(cap.get("text", ""))
        kind = "table" if text.lower().startswith("table") else "figure" if re.match(r"^(fig\.?|figure)", text, re.I) else "visual"
        figures.append({
            "item_id": f"V{idx:04d}",
            "kind": kind,
            "caption": text,
            "caption_anchor": cap.get("anchor", ""),
            "page_hint": str(cap.get("anchor", "")).split(":L")[0] if cap.get("anchor") else "",
        })
    return figures


def _extract_tables(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [b for b in blocks if b.get("type") == "table_row"]
    return [{"table_id": f"T{i+1:04d}", "anchor": row["anchor"], "text": row["text"]} for i, row in enumerate(rows[:1000])]


def _extract_formulas(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [b for b in blocks if b.get("type") == "formula_or_equation"]
    return [{"formula_id": f"E{i+1:04d}", "anchor": row["anchor"], "text": row["text"]} for i, row in enumerate(rows[:1000])]


def _extract_references(packet: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    bib = _load_json(packet / "references" / "bibtex_entries.json")
    for idx, entry in enumerate(bib.get("entries", []) or [], start=1):
        refs.append({"reference_id": f"R{idx:04d}", "source": "bibtex", **entry})
    pdf_refs = _load_json(packet / "derived" / "pdf" / "citation_reference_manifest.json")
    offset = len(refs)
    for idx, entry in enumerate(pdf_refs.get("reference_entries", []) or [], start=1):
        refs.append({"reference_id": f"R{offset+idx:04d}", "source": "pdf_reference_candidate", **entry})
    # GROBID TEI fallback: parse bibliography entries lightly if present.
    for tei_path in sorted((packet / "derived" / "pdf_advanced").glob("**/*.tei.xml")):
        try:
            root = ET.parse(tei_path).getroot()
            ns = {"tei": "http://www.tei-c.org/ns/1.0"}
            for bibl in root.findall(".//tei:listBibl/tei:biblStruct", ns)[:500]:
                title_el = bibl.find(".//tei:title", ns)
                title = "".join(title_el.itertext()).strip() if title_el is not None else ""
                if title:
                    refs.append({"reference_id": f"R{len(refs)+1:04d}", "source": "grobid_tei", "title": title, "tei_file": _rel(tei_path, packet)})
        except Exception:
            continue
    return refs[:2000]


def _write_advanced_markdown(out_dir: Path, blocks: list[dict[str, Any]], figures: list[dict[str, Any]], refs: list[dict[str, Any]]) -> None:
    lines = [
        "# Normalized Document View",
        "",
        "This is a lightweight unified view built from source text, PDF text, PDF visuals, and optional advanced-ingestion outputs. It is intended for reviewer context, not as a canonical reconstruction of the manuscript.",
        "",
        "## High-signal blocks",
        "",
    ]
    for block in blocks[:400]:
        lines.append(f"- `{block['anchor']}` **{block['type']}**: {block['text'][:300]}")
    if figures:
        lines.extend(["", "## Figure/table caption candidates", ""])
        for fig in figures[:200]:
            lines.append(f"- `{fig.get('caption_anchor','')}` **{fig.get('kind','visual')}**: {str(fig.get('caption',''))[:300]}")
    if refs:
        lines.extend(["", "## Reference candidates", ""])
        for ref in refs[:200]:
            title = ref.get("title") or ref.get("text") or ref.get("key") or "[untitled reference]"
            lines.append(f"- `{ref.get('reference_id')}` {str(title)[:300]}")
    (out_dir / "advanced_markdown.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_normalized_document(packet: Path, out_dir: Path | None = None) -> dict[str, Any]:
    packet = Path(packet).resolve()
    target = out_dir or (packet / "derived" / "normalized_document")
    target.mkdir(parents=True, exist_ok=True)
    blocks = _extract_blocks(packet)
    sections = _extract_sections(packet, blocks)
    figures = _extract_figures(packet)
    tables = _extract_tables(blocks)
    formulas = _extract_formulas(blocks)
    references = _extract_references(packet)
    manifest = {
        "version": "v1-normalized-document",
        "status": "ok" if blocks else "no_text_blocks_found",
        "counts": {
            "blocks": len(blocks),
            "sections": len(sections),
            "figures_or_visuals": len(figures),
            "tables_or_table_rows": len(tables),
            "formulas_or_equations": len(formulas),
            "references": len(references),
        },
        "outputs": {
            "blocks": "blocks.json",
            "sections": "sections.json",
            "figures": "figures.json",
            "tables": "tables.json",
            "formulas": "formulas.json",
            "references": "references.json",
            "advanced_markdown": "advanced_markdown.md",
        },
        "notes": "Normalized outputs are approximate and combine multiple extraction sources. Use source anchors for verification.",
    }
    write_json(target / "blocks.json", {"blocks": blocks})
    write_json(target / "sections.json", {"sections": sections})
    write_json(target / "figures.json", {"figures": figures})
    write_json(target / "tables.json", {"tables": tables})
    write_json(target / "formulas.json", {"formulas": formulas})
    write_json(target / "references.json", {"references": references})
    write_json(target / "normalized_document_manifest.json", manifest)
    _write_advanced_markdown(target, blocks, figures, references)
    return manifest
