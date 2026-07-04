from __future__ import annotations

"""Simple, dependency-free DOCX text extraction for review packets.

A ``.docx`` file is a ZIP archive whose main content lives in
``word/document.xml`` (WordprocessingML). This module extracts review-friendly
text from that XML using only the Python standard library (``zipfile`` +
``xml.etree.ElementTree``) so the skill gains real Word coverage without adding a
runtime dependency. It mirrors the output shape of ``pdf_simple`` where practical:

- paragraph-anchored Markdown text (``extracted_docx.md``);
- heading-delimited section chunks (``docx_sections/``);
- a manifest with status, an extraction-quality label, and warnings.

It does not attempt full fidelity (footnotes, comments, tracked changes,
equations, embedded objects). Source LaTeX/Markdown remains preferred when
available; this path makes Word-only submissions reviewable instead of silently
empty.

Security: manuscript files are untrusted input. To avoid decompression-bomb and
XML-entity-expansion abuse, the main document part is size-capped before reading
and parsed with a hardened parser that rejects DTDs/entity declarations. On any
error the extractor degrades gracefully to a ``failed``/``missing_or_invalid``
status with a warning rather than raising.
"""

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

# WordprocessingML main namespace.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# Office Math (OMML) namespace: Word equations are stored here, not as w:t runs.
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

# Decompression-bomb guard: refuse to read a document part larger than this
# uncompressed size (bytes). Real manuscripts are comfortably under this.
_MAX_DOCUMENT_XML_BYTES = 64 * 1024 * 1024  # 64 MB
_MAX_TOTAL_UNCOMPRESSED_BYTES = 256 * 1024 * 1024  # 256 MB across the archive


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section_slug(title: str, fallback: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_")
    return slug[:70] or fallback


def _quality_label(*, status: str, paragraph_count: int, total_chars: int, section_count: int) -> str:
    if status != "ok":
        return "failed"
    if paragraph_count == 0 or total_chars < 200:
        return "weak"
    if section_count == 0 or total_chars < 2000:
        return "usable"
    return "good"


def _hardened_parser() -> ET.XMLParser:
    """Return an XMLParser that refuses DTDs/entity declarations (anti-XXE/bomb).

    Standard ``.docx`` content has no DTD, so rejecting a DOCTYPE declaration blocks
    the custom-entity-definition vector (billion-laughs / XXE) without affecting
    normal WordprocessingML parsing.
    """
    parser = ET.XMLParser()

    def _reject_dtd(*_args, **_kwargs):  # pragma: no cover - defensive
        raise ValueError("DTD/entity declarations are not allowed in manuscript XML")

    try:
        parser.parser.StartDoctypeDeclHandler = _reject_dtd  # type: ignore[attr-defined]
        parser.parser.EntityDeclHandler = _reject_dtd  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - non-expat backend
        pass
    return parser


def _read_document_xml(docx_path: Path) -> str:
    """Read ``word/document.xml`` from the archive with size guards."""
    return _read_part(docx_path, "word/document.xml", required=True)


def _read_part(docx_path: Path, member: str, *, required: bool = False) -> str:
    """Read a named XML part from the .docx archive with size guards.

    Returns "" for an absent optional part; raises for an absent required part.
    """
    with zipfile.ZipFile(docx_path) as zf:
        total = sum(info.file_size for info in zf.infolist())
        if total > _MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("DOCX archive uncompressed size exceeds the safety cap")
        try:
            info = zf.getinfo(member)
        except KeyError as exc:
            if required:
                raise ValueError(f"DOCX has no {member} part") from exc
            return ""
        if info.file_size > _MAX_DOCUMENT_XML_BYTES:
            if required:
                raise ValueError(f"DOCX {member} exceeds the safety cap")
            return ""
        with zf.open(info) as handle:
            return handle.read(_MAX_DOCUMENT_XML_BYTES + 1).decode("utf-8", errors="replace")


def _body_blocks(body: ET.Element):
    """Yield body-level blocks (paragraphs/tables), unwrapping content controls.

    Word content controls (``w:sdt``) wrap real content in ``w:sdtContent``; without
    unwrapping, that text would be missed. Nested sdt wrappers are handled iteratively.
    """
    for child in list(body):
        if child.tag == f"{_W}sdt":
            content = child.find(f"{_W}sdtContent")
            if content is not None:
                yield from _body_blocks(content)
        else:
            yield child


def _extract_media(docx_path: Path, out_root: Path, *, max_files: int = 200, max_bytes: int = 32 * 1024 * 1024) -> list[str]:
    """Extract embedded images (``word/media/*``) from a .docx into ``out_root/media``.

    Word manuscripts have no page-render equivalent, so their figures would otherwise be
    invisible to a visual reviewer. Extracting the embedded media gives the host agent
    (or a visual step) actual image files to inspect. Bounded and fully guarded.
    """
    written: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as zf:
            members = [
                info for info in zf.infolist()
                if info.filename.startswith("word/media/")
                and not info.is_dir()
                and info.file_size <= max_bytes
            ]
            if not members:
                return written
            media_dir = out_root / "media"
            media_dir.mkdir(parents=True, exist_ok=True)
            for info in members[:max_files]:
                name = Path(info.filename).name
                if not name:
                    continue
                try:
                    data = zf.read(info)
                except Exception:
                    continue
                (media_dir / name).write_bytes(data)
                written.append(f"media/{name}")
    except Exception:
        return written
    return sorted(written)


def _extract_notes(docx_path: Path, member: str, tag: str) -> list[str]:
    """Extract non-separator footnote/endnote texts from an optional DOCX part."""
    xml = _read_part(docx_path, member)
    if not xml or re.search(r"<!DOCTYPE", xml, re.IGNORECASE):
        return []
    try:
        root = ET.fromstring(xml, parser=_hardened_parser())
    except Exception:
        return []
    notes: list[str] = []
    skip = {"separator", "continuationSeparator", "continuationNotice"}
    for note in root.findall(f"{_W}{tag}"):
        if note.get(f"{_W}type", "") in skip:
            continue
        text = " ".join(_paragraph_text(p) for p in note.findall(f"{_W}p")).strip()
        if text:
            notes.append(_normalise(text))
    return notes


def _paragraph_text(paragraph: ET.Element) -> str:
    """Concatenate run text within a paragraph, honouring tabs, breaks, and math.

    Office Math (OMML) content is stored in ``m:t`` runs rather than ``w:t``; it is
    included inline so equations are not silently dropped from the review text.
    """
    parts: list[str] = []
    for node in paragraph.iter():
        tag = node.tag
        if tag == f"{_W}t" or tag == f"{_M}t":
            parts.append(node.text or "")
        elif tag == f"{_W}tab":
            parts.append("\t")
        elif tag in (f"{_W}br", f"{_W}cr"):
            parts.append(" ")
    return _normalise("".join(parts))


def _paragraph_style(paragraph: ET.Element) -> str:
    ppr = paragraph.find(f"{_W}pPr")
    if ppr is None:
        return ""
    style = ppr.find(f"{_W}pStyle")
    if style is None:
        return ""
    return style.get(f"{_W}val", "") or ""


def _heading_level(style: str) -> int:
    """Return a heading level (1-9) for a paragraph style, or 0 if not a heading."""
    if not style:
        return 0
    low = style.lower()
    if low in ("title",):
        return 1
    m = re.match(r"heading([1-9])", low)
    if m:
        return int(m.group(1))
    return 0


def _table_rows(table: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.findall(f"{_W}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{_W}tc"):
            cell_text = " ".join(
                _paragraph_text(p) for p in cell.findall(f"{_W}p")
            ).strip()
            cells.append(_normalise(cell_text))
        if any(cells):
            rows.append(cells)
    return rows


def extract_docx_to_markdown(docx_path: Path, out_root: Path) -> dict[str, Any]:
    """Extract a ``.docx`` manuscript into review-friendly, anchored Markdown.

    Returns a manifest describing status, quality, and generated files. Never
    raises for a malformed or oversized document; instead it records the failure
    in the manifest so packet building continues.
    """
    docx_path = Path(docx_path).resolve()
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "source_docx": docx_path.name,
        "method": "stdlib-zip-xml-simple-text",
        "status": "not_run",
        "extraction_quality": "failed",
        "paragraph_count": 0,
        "heading_count": 0,
        "table_count": 0,
        "sections": [],
        "warnings": [],
    }

    if not zipfile.is_zipfile(docx_path):
        manifest["status"] = "missing_or_invalid"
        manifest["warnings"].append(
            "File is not a valid .docx (ZIP) archive. If this is a legacy .doc file, "
            "re-save it as .docx, or provide LaTeX/Markdown/PDF source."
        )
        (out_root / "docx_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    try:
        xml_text = _read_document_xml(docx_path)
        # Defense-in-depth: a legitimate .docx never declares a DTD/DOCTYPE, so any
        # DOCTYPE is a red flag for entity-expansion/XXE abuse. Reject before parsing.
        if re.search(r"<!DOCTYPE", xml_text, re.IGNORECASE):
            raise ValueError("DTD/DOCTYPE declarations are not allowed in manuscript XML")
        root = ET.fromstring(xml_text, parser=_hardened_parser())
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["warnings"].append(f"Could not read/parse DOCX content: {exc}")
        (out_root / "docx_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    body = root.find(f"{_W}body")
    if body is None:
        manifest["status"] = "failed"
        manifest["warnings"].append("DOCX document body not found.")
        (out_root / "docx_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    md_lines: list[str] = [
        f"# Extracted DOCX Text: {docx_path.name}",
        "",
        "Extraction method: simple DOCX text extraction (stdlib) with paragraph anchors.",
        "Use `PARA` anchors for evidence-grounded review. Prefer LaTeX/Markdown source when available.",
        "",
        "```text",
    ]
    section_chunks: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    para_index = 0
    heading_count = 0
    table_count = 0
    total_chars = 0

    # Iterate the body's blocks in document order (paragraphs + tables), unwrapping
    # content controls so wrapped content is not silently dropped.
    for child in _body_blocks(body):
        tag = child.tag
        if tag == f"{_W}p":
            text = _paragraph_text(child)
            if not text:
                continue
            para_index += 1
            total_chars += len(text)
            anchor = f"{docx_path.name}:para{para_index}"
            level = _heading_level(_paragraph_style(child))
            md_lines.append(f"PARA{para_index}: {text}")
            if level:
                heading_count += 1
                if current_section and current_section.get("lines"):
                    section_chunks.append(current_section)
                current_section = {
                    "title": text,
                    "level": level,
                    "start_anchor": anchor,
                    "lines": [f"{anchor}: {text}"],
                }
            elif current_section is not None:
                current_section["lines"].append(f"{anchor}: {text}")
        elif tag == f"{_W}tbl":
            rows = _table_rows(child)
            if not rows:
                continue
            table_count += 1
            # Emit a table marker, then one anchored line per row so table structure
            # (and per-row anchors) is preserved rather than flattened to a single line.
            para_index += 1
            marker_anchor = f"{docx_path.name}:para{para_index}"
            md_lines.append(f"PARA{para_index}: [TABLE {table_count}]")
            if current_section is not None:
                current_section["lines"].append(f"{marker_anchor}: [TABLE {table_count}]")
            for row in rows[:200]:
                para_index += 1
                line = " | ".join(row)
                total_chars += len(line)
                row_anchor = f"{docx_path.name}:para{para_index}"
                md_lines.append(f"PARA{para_index}: {line}")
                if current_section is not None:
                    current_section["lines"].append(f"{row_anchor}: {line}")

    if current_section and current_section.get("lines"):
        section_chunks.append(current_section)

    # Footnotes / endnotes live in separate parts and often carry substantive
    # academic content; append them so they are reviewable.
    footnotes = _extract_notes(docx_path, "word/footnotes.xml", "footnote")
    endnotes = _extract_notes(docx_path, "word/endnotes.xml", "endnote")
    note_count = len(footnotes) + len(endnotes)
    for j, note in enumerate(footnotes + endnotes, start=1):
        para_index += 1
        total_chars += len(note)
        md_lines.append(f"PARA{para_index}: [NOTE {j}] {note}")

    md_lines.extend(["```", ""])
    (out_root / "extracted_docx.md").write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    sections_dir = out_root / "docx_sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    for idx, section in enumerate(section_chunks, start=1):
        title = str(section.get("title") or f"Section {idx}")
        fname = f"{idx:02d}_{_section_slug(title, f'section_{idx}')}.md"
        body_lines = [f"# {title}", "", f"Start anchor: `{section.get('start_anchor')}`", "", "```text"]
        body_lines.extend(section.get("lines", []))
        body_lines.append("```")
        (sections_dir / fname).write_text("\n".join(body_lines) + "\n", encoding="utf-8")
        manifest["sections"].append(
            {"title": title, "file": f"docx_sections/{fname}", "start_anchor": section.get("start_anchor")}
        )

    manifest["status"] = "ok"
    manifest["paragraph_count"] = para_index
    manifest["heading_count"] = heading_count
    manifest["table_count"] = table_count
    manifest["note_count"] = note_count
    manifest["formula_count"] = sum(1 for _ in body.iter(f"{_M}oMath"))
    media_files = _extract_media(docx_path, out_root)
    manifest["media_files"] = media_files
    manifest["image_count"] = len(media_files)
    if media_files:
        manifest["warnings"].append(
            f"Extracted {len(media_files)} embedded image(s) to `media/`; a visual reviewer "
            "or the host agent should inspect them for figure/chart evidence."
        )
    manifest["total_text_chars"] = total_chars
    manifest["section_count"] = len(manifest["sections"])
    manifest["extraction_quality"] = _quality_label(
        status="ok",
        paragraph_count=para_index,
        total_chars=total_chars,
        section_count=len(manifest["sections"]),
    )
    if not manifest["sections"]:
        manifest["warnings"].append(
            "No heading styles detected; reviewers should cite PARA anchors. Word documents "
            "without heading styles yield a flat text stream."
        )
    if manifest["extraction_quality"] in {"weak", "usable"}:
        manifest["warnings"].append(
            f"Extraction quality is {manifest['extraction_quality']}; prefer LaTeX/Markdown source when available."
        )
    (out_root / "docx_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
