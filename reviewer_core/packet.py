from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import shutil
from typing import Iterable

from .io_utils import sha256_file, read_text, write_json, slugify, line_anchor, TEXT_EXTS
from .pdf_simple import extract_pdf_to_markdown
from .docx_simple import extract_docx_to_markdown
from .doc_legacy import extract_doc_to_markdown
from .advanced_ingestion import run_advanced_ingestion
from .retrieval import build_query_plan
from .coverage import audit_review_packet
from .figure_table import write_figure_table_matrix
from .citation_claim import write_citation_claim_matrix
from .normalized_document import build_normalized_document

DOC_EXTS = {".pdf", ".docx", ".doc"}
TABLE_EXTS = {".csv", ".tsv", ".xlsx", ".xls"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".tif", ".tiff"}
BIB_EXTS = {".bib", ".ris", ".enw"}

SECTION_KEYWORDS = {
    "abstract": "01_abstract",
    "introduction": "02_introduction",
    "related": "03_related_work",
    "background": "03_related_work",
    "method": "04_method",
    "approach": "04_method",
    "experiment": "05_experiments",
    "evaluation": "05_experiments",
    "result": "06_results",
    "discussion": "07_discussion",
    "limitation": "08_limitations",
    "conclusion": "09_conclusion",
    "appendix": "10_appendix",
    "supplement": "10_appendix",
}

INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
SECTION_RE = re.compile(r"^\\(part|chapter|section|subsection|subsubsection|paragraph)\*?\{(.+?)\}")
CAPTION_RE = re.compile(r"\\caption(?:\[[^\]]*\])?\{(.+?)\}", re.S)
LABEL_RE = re.compile(r"\\label\{(.+?)\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|citealp|parencite|textcite|autocite)(?:\[[^\]]*\])*\{([^}]+)\}")
BIB_ENTRY_RE = re.compile(r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,]+),", re.I)
FIELD_RE = re.compile(r"(?P<field>title|author|year|journal|booktitle|doi|url)\s*=\s*[\{\"](?P<value>.*?)[\}\"]\s*,", re.I | re.S)
ENV_RE = re.compile(r"\\begin\{(table\*?|figure\*?|equation\*?|align\*?|algorithm\*?)\}")



def _is_relative_to(path: Path, root: Path) -> bool:
    """Return True only when path is inside root after resolution."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _display_path(path: Path, root: Path) -> str:
    """Display packet/build paths without leaking absolute local paths."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return "[outside-project]"

@dataclass
class CopiedFile:
    original: str
    packet_path: str
    category: str
    sha256: str
    chars: int


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
                continue
            yield path


def classify(path: Path) -> str:
    name = path.stem.lower()
    suffix = path.suffix.lower()
    if suffix in BIB_EXTS or "reference" in name or "bibliography" in name:
        return "references"
    if suffix in TABLE_EXTS or "table" in name:
        return "tables"
    if suffix in IMAGE_EXTS or "figure" in name or "fig" in name:
        return "figures"
    if suffix in DOC_EXTS:
        return "source_documents"
    if suffix in TEXT_EXTS:
        for keyword, folder in SECTION_KEYWORDS.items():
            if keyword in name:
                return f"sections/{folder}"
        return "sections/00_full_or_uncategorised"
    return "misc"


def copy_file(src: Path, out_root: Path, input_root: Path) -> CopiedFile:
    category = classify(src)
    dest_dir = out_root / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = src.name.replace(" ", "_")
    dest = dest_dir / safe_name
    if dest.exists():
        counter = 2
        while dest.exists():
            dest = dest_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
    shutil.copy2(src, dest)
    chars = len(read_text(src)) if src.suffix.lower() in TEXT_EXTS else 0
    return CopiedFile(
        original=str(src.relative_to(input_root)),
        packet_path=str(dest.relative_to(out_root)),
        category=category,
        sha256=sha256_file(dest),
        chars=chars,
    )


def resolve_latex_project(main_tex: Path, max_depth: int = 8, project_root: Path | None = None) -> tuple[str, list[dict]]:
    r"""Resolve simple LaTeX \input and \include statements into one text stream.

    Security model:
    - Manuscript text is untrusted input.
    - Included files are sandboxed to project_root, which defaults to main_tex.parent.
    - Absolute paths, parent-directory traversal, symlink escapes, directories, and
      non-.tex includes are rejected and recorded instead of being read.

    This prevents a malicious manuscript from using \input{/etc/passwd} or
    \input{../../secret} to splice local files into the review packet and then
    send them to a configured remote model provider.
    """
    root = (project_root or main_tex.parent).expanduser().resolve()
    main_resolved = main_tex.expanduser().resolve()
    if not _is_relative_to(main_resolved, root):
        raise ValueError(f"main_tex must be inside the LaTeX project root: {main_tex}")

    seen: set[Path] = set()
    included: list[dict] = []

    def _resolve(path: Path, depth: int) -> str:
        resolved = path.expanduser().resolve()
        display = _display_path(resolved, root)
        if not _is_relative_to(resolved, root):
            included.append({"file": display, "status": "rejected_outside_project_root"})
            return f"\n% [input rejected: outside project root]\n"
        if depth > max_depth:
            included.append({"file": display, "status": "max_depth_exceeded"})
            return f"\n% [input skipped: max depth exceeded for {display}]\n"
        if resolved in seen:
            included.append({"file": display, "status": "already_seen"})
            return f"\n% [input skipped: already included {display}]\n"
        if not resolved.is_file():
            included.append({"file": display, "status": "missing_or_not_file"})
            return f"\n% [input skipped: missing or not a file: {display}]\n"
        if resolved.suffix.lower() != ".tex":
            included.append({"file": display, "status": "rejected_unsupported_extension"})
            return f"\n% [input rejected: unsupported extension for {display}]\n"

        seen.add(resolved)
        text = resolved.read_text(encoding="utf-8", errors="replace")
        included.append({"file": display, "status": "included", "chars": len(text)})

        def repl(match: re.Match[str]) -> str:
            raw = match.group(1).strip()
            raw_path = Path(raw)
            if raw_path.is_absolute():
                included.append({"raw": raw, "status": "rejected_absolute_path"})
                return f"\n% [input rejected: absolute path {raw}]\n"

            candidate = path.parent / raw_path
            if candidate.suffix == "":
                candidate = candidate.with_suffix(".tex")
            candidate_resolved = candidate.expanduser().resolve(strict=False)
            candidate_display = _display_path(candidate_resolved, root)

            if not _is_relative_to(candidate_resolved, root):
                included.append({"raw": raw, "file": candidate_display, "status": "rejected_outside_project_root"})
                return f"\n% [input rejected: outside project root: {raw}]\n"
            if candidate_resolved.suffix.lower() != ".tex":
                included.append({"raw": raw, "file": candidate_display, "status": "rejected_unsupported_extension"})
                return f"\n% [input rejected: unsupported extension: {raw}]\n"
            if not candidate_resolved.exists() or not candidate_resolved.is_file():
                included.append({"raw": raw, "file": candidate_display, "status": "missing"})
                return f"\n% [missing input: {raw}]\n"
            return "\n" + _resolve(candidate_resolved, depth + 1) + "\n"

        return INPUT_RE.sub(repl, text)

    return _resolve(main_resolved, 0), included


def split_latex_text(text: str, source_name: str, out_dir: Path) -> dict:
    lines = text.splitlines()
    out_dir.mkdir(parents=True, exist_ok=True)
    sections: list[dict] = []
    current = {"level": "front", "title": "Front Matter", "start_line": 1, "lines": []}
    for i, line in enumerate(lines, 1):
        match = SECTION_RE.match(line.strip())
        if match:
            if current["lines"]:
                sections.append(current)
            current = {"level": match.group(1), "title": match.group(2), "start_line": i, "lines": [line]}
        else:
            current["lines"].append(line)
    if current["lines"]:
        sections.append(current)

    manifest = {"source": source_name, "sections": []}
    for idx, sec in enumerate(sections, 1):
        end_line = sec["start_line"] + len(sec["lines"]) - 1
        fname = f"{idx:02d}_{slugify(sec['title'], 'section')}.md"
        anchor = f"{source_name}:L{sec['start_line']}-L{end_line}"
        numbered = "\n".join(f"L{sec['start_line'] + offset}: {line}" for offset, line in enumerate(sec["lines"]))
        body = f"# {sec['title']}\n\nSource anchor: `{anchor}`\n\n```latex\n{numbered}\n```\n"
        (out_dir / fname).write_text(body, encoding="utf-8")
        manifest["sections"].append({"file": fname, "title": sec["title"], "level": sec["level"], "anchor": anchor})
    write_json(out_dir / "section_manifest.json", manifest)
    return manifest


def extract_tex_assets_from_text(text: str, source_name: str) -> dict:
    lines = text.splitlines()
    assets: list[dict] = []
    citations: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        for cite in CITE_RE.finditer(line):
            keys = [k.strip() for k in cite.group(1).split(",") if k.strip()]
            for key in keys:
                citations.append({"key": key, "anchor": f"{source_name}:L{i+1}"})
        env_match = ENV_RE.search(line)
        if env_match:
            env = env_match.group(1)
            start = i + 1
            block = [line]
            i += 1
            end_re = re.compile(r"\\end\{" + re.escape(env) + r"\}")
            while i < len(lines):
                block.append(lines[i])
                if end_re.search(lines[i]):
                    break
                i += 1
            end = i + 1
            text_block = "\n".join(block)
            caption = CAPTION_RE.search(text_block)
            label = LABEL_RE.search(text_block)
            assets.append({
                "type": env,
                "label": label.group(1) if label else "",
                "caption": re.sub(r"\s+", " ", caption.group(1)).strip() if caption else "",
                "anchor": f"{source_name}:L{start}-L{end}",
            })
        i += 1
    return {"source": source_name, "assets": assets, "citations": citations}


def parse_bibtex(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    entries: list[dict] = []
    positions = list(BIB_ENTRY_RE.finditer(text))
    for idx, match in enumerate(positions):
        start = match.start()
        end = positions[idx + 1].start() if idx + 1 < len(positions) else len(text)
        block = text[start:end]
        fields = {m.group("field").lower(): re.sub(r"\s+", " ", m.group("value")).strip() for m in FIELD_RE.finditer(block)}
        entries.append({"key": match.group("key").strip(), "type": match.group("type"), **fields})
    return entries


def build_packet(
    input_root: Path,
    out_root: Path,
    venue: str = "",
    field: str = "",
    mode: str = "standard",
    overwrite: bool = False,
    pdf_text: str = "auto",
    pdf_visuals: str = "auto",
    pdf_engine: str = "simple",
    grobid_endpoint: str = "http://localhost:8070",
    render_dpi: int = 120,
    max_render_pages: int = 30,
    max_embedded_images: int = 200,
) -> dict:
    input_root = input_root.expanduser().resolve()
    out_root = out_root.expanduser().resolve()
    if not input_root.exists() or not input_root.is_dir():
        raise FileNotFoundError(f"Input folder does not exist or is not a directory: {input_root}")
    if out_root.exists() and overwrite:
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    copied: list[CopiedFile] = []
    for file in iter_files(input_root):
        try:
            file.relative_to(out_root)
            continue
        except ValueError:
            pass
        copied.append(copy_file(file, out_root, input_root))

    main_tex_candidates = [input_root / name for name in ("main.tex", "paper.tex", "manuscript.tex") if (input_root / name).exists()]
    if not main_tex_candidates:
        main_tex_candidates = list(input_root.glob("*.tex"))[:1]

    pdf_candidates = [p for p in input_root.rglob("*.pdf") if p.is_file()]
    # Word inputs. Skip Word lock/temp files ("~$..."). Legacy binary .doc cannot be
    # parsed without external tools, so it is recorded as a warning rather than read.
    docx_candidates = [
        p for p in input_root.rglob("*.docx")
        if p.is_file() and not p.name.startswith("~$")
    ]
    legacy_doc_candidates = [
        p for p in input_root.rglob("*.doc")
        if p.is_file() and p.suffix.lower() == ".doc" and not p.name.startswith("~$")
    ]

    latex_manifest = None
    asset_manifest = None
    pdf_manifest = None
    advanced_pdf_manifest = None
    docx_manifest = None
    doc_manifest = None
    legacy_doc_notices: list[str] = []
    if main_tex_candidates:
        main_tex = main_tex_candidates[0]
        resolved_text, included = resolve_latex_project(main_tex, project_root=input_root)
        resolved_dir = out_root / "derived"
        resolved_dir.mkdir(parents=True, exist_ok=True)
        (resolved_dir / "resolved_manuscript.tex").write_text(resolved_text, encoding="utf-8")
        write_json(resolved_dir / "latex_inputs.json", {"main": str(main_tex.relative_to(input_root)), "included": included})
        latex_manifest = split_latex_text(resolved_text, "resolved_manuscript.tex", out_root / "derived" / "sections")
        asset_manifest = extract_tex_assets_from_text(resolved_text, "resolved_manuscript.tex")
        write_json(out_root / "derived" / "asset_manifest.json", asset_manifest)

    if pdf_text not in {"auto", "off", "force"}:
        raise ValueError("pdf_text must be one of: auto, off, force")
    if pdf_visuals not in {"auto", "off", "force"}:
        raise ValueError("pdf_visuals must be one of: auto, off, force")
    if pdf_engine not in {"simple", "off", "auto", "docling", "marker", "grobid"}:
        raise ValueError("pdf_engine must be one of: simple, off, auto, docling, marker, grobid")
    # PDF is a first-class manuscript input: when a PDF is present, auto mode
    # extracts lightweight page/line anchored text even if LaTeX/Markdown source
    # also exists. Source sections remain preferred for reasoning; PDF anchors
    # give page-grounded evidence locations for review.
    should_extract_pdf = bool(pdf_candidates) and pdf_text != "off"
    should_extract_visuals = bool(pdf_candidates) and pdf_visuals != "off"
    if should_extract_pdf or should_extract_visuals:
        pdf_manifest = extract_pdf_to_markdown(
            pdf_candidates[0],
            out_root / "derived" / "pdf",
            extract_visuals=should_extract_visuals,
            render_dpi=render_dpi,
            max_render_pages=max_render_pages,
            max_embedded_images=max_embedded_images,
        )

    # Optional advanced PDF ingestion is intentionally opt-in. It can enrich the
    # packet with stronger Markdown/JSON/TEI outputs when external tools are
    # installed, while keeping the core skill lightweight and functional.
    if pdf_candidates and pdf_engine not in {"simple", "off"}:
        advanced_pdf_manifest = run_advanced_ingestion(
            pdf_candidates[0],
            out_root / "derived" / "pdf_advanced",
            pdf_engine,
            grobid_endpoint=grobid_endpoint,
        )

    # Word (.docx) is a first-class manuscript input. When a .docx is present we
    # extract paragraph/heading-anchored text (stdlib only) so Word-only
    # submissions are reviewable instead of silently empty. Legacy binary .doc
    # cannot be parsed without external tools and is surfaced as a notice.
    if docx_candidates:
        docx_manifest = extract_docx_to_markdown(
            docx_candidates[0], out_root / "derived" / "docx"
        )
    if legacy_doc_candidates:
        doc_manifest = extract_doc_to_markdown(
            legacy_doc_candidates[0], out_root / "derived" / "doc"
        )
        if doc_manifest.get("status") != "ok":
            legacy_doc_notices = [
                f"Legacy .doc file '{p.name}' could not be text-extracted; install "
                f"'antiword'/'olefile' or re-save it as .docx for full coverage."
                for p in legacy_doc_candidates
            ]

    bib_entries: list[dict] = []
    for bib in input_root.rglob("*.bib"):
        if bib.is_file():
            bib_entries.extend(parse_bibtex(bib))
    if bib_entries:
        write_json(out_root / "references" / "bibtex_entries.json", {"entries": bib_entries})

    manifest = {
        "version": "v1",
        "target_venue": venue,
        "field_or_domain": field,
        "mode": mode,
        "input_root": "[redacted]",
        "input_root_name": input_root.name,
        "files": [c.__dict__ for c in copied],
        "latex_manifest": latex_manifest,
        "asset_manifest": asset_manifest,
        "pdf_manifest": pdf_manifest,
        "advanced_pdf_manifest": advanced_pdf_manifest,
        "docx_manifest": docx_manifest,
        "doc_manifest": doc_manifest,
        "legacy_doc_notices": legacy_doc_notices,
        "pdf_text_mode": pdf_text,
        "pdf_visuals_mode": pdf_visuals,
        "pdf_engine": pdf_engine,
        "bibtex_entry_count": len(bib_entries),
        "confidentiality": "author-owned manuscript assumed; verify before use",
    }

    # Generate a local prior-work query plan from title/abstract/keywords. This
    # does not call the internet and does not send full manuscript text anywhere.
    try:
        query_plan = build_query_plan(out_root, out_path=out_root / "prior_work" / "query_plan.json")
        manifest["prior_work_query_plan"] = "prior_work/query_plan.json"
        manifest["prior_work_query_count"] = len(query_plan.get("queries", []))
    except Exception as exc:
        manifest["prior_work_query_plan_error"] = str(exc)

    write_json(out_root / "manifest.json", manifest)
    write_index(out_root, manifest)

    # Build review scaffolds that connect non-textual and citation evidence to
    # manuscript claims. These are lightweight and local; they do not call LLMs.
    try:
        ft_report = write_figure_table_matrix(out_root)
        manifest["figure_table_evidence_matrix"] = "coverage/figure_table_evidence_matrix.md"
        manifest["figure_table_entry_count"] = ft_report.get("entry_count", 0)
    except Exception as exc:
        manifest["figure_table_evidence_matrix_error"] = str(exc)
    try:
        cc_report = write_citation_claim_matrix(out_root)
        manifest["citation_claim_matrix"] = "coverage/citation_claim_matrix.md"
        manifest["citation_claim_entry_count"] = cc_report.get("entry_count", 0)
    except Exception as exc:
        manifest["citation_claim_matrix_error"] = str(exc)

    try:
        nd_manifest = build_normalized_document(out_root)
        manifest["normalized_document"] = "derived/normalized_document/normalized_document_manifest.json"
        manifest["normalized_document_status"] = nd_manifest.get("status")
        manifest["normalized_document_counts"] = nd_manifest.get("counts", {})
    except Exception as exc:
        manifest["normalized_document_error"] = str(exc)

    try:
        coverage_report = audit_review_packet(out_root, write_files=True)
        manifest["coverage_report"] = "coverage/coverage_report.md"
        manifest["coverage_status"] = coverage_report.get("overall_status")
        write_json(out_root / "manifest.json", manifest)
        write_index(out_root, manifest)
    except Exception as exc:
        manifest["coverage_report_error"] = str(exc)
        write_json(out_root / "manifest.json", manifest)
    return manifest


def write_index(out_root: Path, manifest: dict) -> None:
    lines = ["# Review Packet Index", "", "## Metadata", ""]
    lines.append(f"- Target venue: {manifest.get('target_venue') or 'not specified'}")
    lines.append(f"- Field/domain: {manifest.get('field_or_domain') or 'not specified'}")
    lines.append(f"- Suggested review mode: {manifest.get('mode')}")
    lines.append("- Confidentiality: author-owned manuscript assumed; verify before use")
    lines.append("")
    lines.append("## Files")
    lines.append("| Category | Packet path | Original path | Chars | SHA-256 |")
    lines.append("|---|---|---|---:|---|")
    for item in manifest.get("files", []):
        lines.append(f"| {item['category']} | `{item['packet_path']}` | `{item['original']}` | {item['chars']} | `{item['sha256'][:12]}...` |")
    if manifest.get("latex_manifest"):
        lines.extend(["", "## Derived LaTeX sections"])
        lines.append("| Section | Anchor | File |")
        lines.append("|---|---|---|")
        for section in manifest["latex_manifest"].get("sections", []):
            lines.append(f"| {section['title']} | `{section['anchor']}` | `derived/sections/{section['file']}` |")
    if manifest.get("pdf_manifest"):
        lines.extend(["", "## Derived PDF text"])
        pdf_manifest = manifest["pdf_manifest"]
        lines.append(f"- Status: `{pdf_manifest.get('status')}`")
        lines.append(f"- Method: `{pdf_manifest.get('method')}`")
        lines.append(f"- Extraction quality: `{pdf_manifest.get('extraction_quality', 'unknown')}`")
        if pdf_manifest.get("status") == "ok":
            lines.append("- Full extracted text: `derived/pdf/extracted_pdf.md`")
            lines.append("- Section-like chunks: `derived/pdf/pdf_sections/`")
            tbl = pdf_manifest.get("table_assets") or {}
            if tbl.get("table_count"):
                lines.append(f"- Structured tables: `derived/pdf/pdf_tables.md` ({tbl.get('table_count')} detected)")
            meta = pdf_manifest.get("document_metadata") or {}
            if meta:
                shown = ", ".join(f"{k}={str(v)[:60]}" for k, v in meta.items())
                lines.append(f"- Document metadata: {shown}")
            if pdf_manifest.get("visual_assets"):
                visuals = pdf_manifest.get("visual_assets") or {}
                lines.append(f"- Visual extraction quality: `{visuals.get('visual_extraction_quality', 'unknown')}`")
                lines.append(f"- Page render images: `{visuals.get('page_image_count', 0)}`")
                lines.append(f"- Embedded images: `{visuals.get('embedded_image_count', 0)}`")
                lines.append("- Visual index: `derived/pdf/visual_index.md`")
        for warning in pdf_manifest.get("warnings", []):
            lines.append(f"- Warning: {warning}")
    if manifest.get("advanced_pdf_manifest"):
        adv = manifest.get("advanced_pdf_manifest") or {}
        lines.extend(["", "## Optional advanced PDF ingestion"])
        lines.append(f"- Engine: `{adv.get('engine', manifest.get('pdf_engine', 'unknown'))}`")
        lines.append(f"- Status: `{adv.get('status', 'unknown')}`")
        if adv.get("outputs"):
            lines.append("- Outputs are available under `derived/pdf_advanced/` and are included in workflow context when text-like.")
        for warning in adv.get("warnings", [])[:10]:
            lines.append(f"- Warning: {warning}")
    if manifest.get("pdf_manifest") and (manifest["pdf_manifest"].get("citation_reference_assets") or {}):
        lines.extend(["", "## PDF citation/reference candidates"])
        cr = manifest["pdf_manifest"].get("citation_reference_assets") or {}
        lines.append(f"- Citation markers: `{cr.get('citation_marker_count', 0)}`")
        lines.append(f"- Reference entries: `{cr.get('reference_entry_count', 0)}`")
        lines.append(f"- Unresolved numeric citations: `{cr.get('unresolved_numeric_citation_count', 0)}`")
        lines.append("- Citation/reference index: `derived/pdf/citation_reference_index.md`")
    if manifest.get("docx_manifest"):
        dm = manifest.get("docx_manifest") or {}
        lines.extend(["", "## Derived Word (DOCX) text"])
        lines.append(f"- Status: `{dm.get('status')}`")
        lines.append(f"- Extraction quality: `{dm.get('extraction_quality', 'unknown')}`")
        if dm.get("status") == "ok":
            lines.append("- Full extracted text: `derived/docx/extracted_docx.md`")
            lines.append(f"- Paragraphs: `{dm.get('paragraph_count', 0)}` | headings: `{dm.get('heading_count', 0)}` | tables: `{dm.get('table_count', 0)}`")
            if dm.get("image_count"):
                lines.append(f"- Embedded images: `{dm.get('image_count')}` under `derived/docx/media/`")
            if dm.get("sections"):
                lines.append("- Heading sections: `derived/docx/docx_sections/`")
        for warning in dm.get("warnings", [])[:10]:
            lines.append(f"- Warning: {warning}")
    if manifest.get("doc_manifest"):
        dc = manifest.get("doc_manifest") or {}
        lines.extend(["", "## Derived legacy Word (.doc) text"])
        lines.append(f"- Status: `{dc.get('status')}`")
        lines.append(f"- Method: `{dc.get('method')}`")
        lines.append(f"- Extraction quality: `{dc.get('extraction_quality', 'unknown')}`")
        if dc.get("status") == "ok":
            lines.append("- Full extracted text: `derived/doc/extracted_doc.md`")
            lines.append(f"- Paragraph blocks: `{dc.get('paragraph_count', 0)}`")
        for warning in dc.get("warnings", [])[:10]:
            lines.append(f"- Warning: {warning}")
    if manifest.get("legacy_doc_notices"):
        lines.extend(["", "## Legacy .doc notices"])
        for notice in manifest.get("legacy_doc_notices", [])[:10]:
            lines.append(f"- {notice}")
    if manifest.get("coverage_report"):
        lines.extend(["", "## Coverage audit"])
        lines.append(f"- Coverage status: `{manifest.get('coverage_status', 'unknown')}`")
        lines.append("- Coverage report: `coverage/coverage_report.md`")
    if manifest.get("figure_table_evidence_matrix") or manifest.get("citation_claim_matrix"):
        lines.extend(["", "## Evidence alignment scaffolds"])
        if manifest.get("figure_table_evidence_matrix"):
            lines.append(f"- Figure/table evidence matrix: `{manifest.get('figure_table_evidence_matrix')}` ({manifest.get('figure_table_entry_count', 0)} entries)")
        if manifest.get("citation_claim_matrix"):
            lines.append(f"- Citation-claim matrix: `{manifest.get('citation_claim_matrix')}` ({manifest.get('citation_claim_entry_count', 0)} entries)")
    if manifest.get("normalized_document"):
        lines.extend(["", "## Normalized document view"])
        lines.append(f"- Normalized manifest: `{manifest.get('normalized_document')}`")
        lines.append("- Normalized Markdown: `derived/normalized_document/advanced_markdown.md`")
        lines.append(f"- Status: `{manifest.get('normalized_document_status', 'unknown')}`")
    if manifest.get("prior_work_query_plan"):
        lines.extend(["", "## Prior-work query plan"])
        lines.append(f"- Generated local query plan: `{manifest.get('prior_work_query_plan')}`")
        lines.append(f"- Candidate queries: {manifest.get('prior_work_query_count', 0)}")
        lines.append("- Privacy note: queries are short title/abstract/keyword strings; full manuscript text is not sent by packet building.")
    lines.extend([
        "",
        "## Recommended review sequence",
        "1. Manuscript Packet Audit",
        "2. Prompt-Injection Sanitization",
        "3. Paper Map",
        "4. Claim-Evidence Matrix",
        "5. Specialist Reviews",
        "6. Review-Quality Audit",
        "7. Meta-Review",
        "8. Revision Patch Plan",
        "",
        "## Reviewer rules",
        "- Prefer author-provided LaTeX/Markdown sections for reasoning, but use PDF page/line anchors whenever useful for page-grounded evidence.",
        "- Every P0/P1 issue must include a concrete evidence anchor or be downgraded to information_gap.",
        "- Do not invent missing citations, policies, results, or evidence.",
    ])
    (out_root / "REVIEW_PACKET_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_context(packet_dir: Path, max_chars_per_file: int = 12000, max_total_chars: int = 120000) -> str:
    packet_dir = packet_dir.resolve()
    candidates: list[Path] = []
    for rel in ["REVIEW_PACKET_INDEX.md", "manifest.json"]:
        p = packet_dir / rel
        if p.exists():
            candidates.append(p)
    for pattern in ["derived/sections/*.md", "derived/pdf/pdf_sections/*.md", "derived/pdf/extracted_pdf.md", "derived/pdf/pdf_tables.md", "derived/pdf/visual_index.md", "derived/pdf/visual_manifest.json", "derived/pdf/citation_reference_index.md", "derived/pdf/citation_reference_manifest.json", "derived/docx/extracted_docx.md", "derived/docx/docx_sections/*.md", "derived/docx/docx_extraction_manifest.json", "derived/doc/extracted_doc.md", "derived/doc/doc_extraction_manifest.json", "derived/pdf_advanced/**/*.md", "derived/pdf_advanced/**/*.json", "derived/pdf_advanced/**/*.xml", "derived/normalized_document/*.md", "derived/normalized_document/*.json", "coverage/coverage_report.md", "coverage/coverage_manifest.json", "coverage/figure_table_evidence_matrix.md", "coverage/figure_table_evidence_matrix.json", "coverage/citation_claim_matrix.md", "coverage/citation_claim_matrix.json", "sections/**/*.md", "sections/**/*.tex", "sections/**/*.txt", "references/*.json", "references/*.bib", "tables/*"]:
        candidates.extend(sorted(packet_dir.glob(pattern)))
    chunks: list[str] = []
    total = 0
    for path in candidates:
        if path.is_file() and path.suffix.lower() in TEXT_EXTS.union({".json"}):
            try:
                text = read_text(path, max_chars=max_chars_per_file)
            except Exception:
                continue
            header = f"\n\n--- FILE: {path.relative_to(packet_dir)} ---\n"
            chunk = header + text
            if total + len(chunk) > max_total_chars:
                remaining = max_total_chars - total
                if remaining <= 0:
                    break
                chunks.append(chunk[:remaining] + "\n[CONTEXT TRUNCATED]")
                break
            chunks.append(chunk)
            total += len(chunk)
    return "".join(chunks)
