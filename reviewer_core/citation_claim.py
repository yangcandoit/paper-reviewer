from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import re

from .io_utils import read_text, write_json, TEXT_EXTS

NUMERIC_CITE_RE = re.compile(r"\[(\d+(?:\s*[-,;]\s*\d+)*)\]")
AUTHOR_YEAR_RE = re.compile(r"\(([A-Z][A-Za-z'`-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?(?:\s*;\s*[A-Z][A-Za-z'`-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?){0,5})\)")
TEXTUAL_AUTHOR_YEAR_RE = re.compile(r"\b([A-Z][A-Za-z'`-]+\s+et\s+al\.)\s*\((\d{4}[a-z]?)\)")
KEY_CITE_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9_:\-]+(?:\s*[,;]\s*[A-Za-z][A-Za-z0-9_:\-]+)*)\]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

CLAIM_VERBS = {
    "show", "shows", "shown", "demonstrate", "demonstrates", "demonstrated", "suggest", "suggests",
    "indicate", "indicates", "find", "finds", "found", "report", "reports", "reported", "argue", "argues",
    "propose", "proposes", "proposed", "achieve", "achieves", "outperform", "outperforms", "improve", "improves",
}


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _packet_text_files(packet: Path) -> list[Path]:
    patterns = [
        "derived/resolved_manuscript.tex",
        "derived/pdf/extracted_pdf.md",
        "derived/sections/*.md",
        "derived/pdf/pdf_sections/*.md",
        "sections/**/*.md",
        "sections/**/*.tex",
        "sections/**/*.txt",
    ]
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in patterns:
        for path in sorted(packet.glob(pattern)):
            if path.is_file() and path not in seen and path.suffix.lower() in TEXT_EXTS.union({".tex"}):
                seen.add(path)
                files.append(path)
    return files


def _clean_line(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\b(?:L\d+|P\d+L\d+|[^\s:]+\.pdf:p\d+:L\d+):\s*", "", text)
    text = re.sub(r"\\(?:cite|citep|citet|citealp|parencite|textcite|autocite)(?:\[[^\]]*\])*\{([^}]+)\}", r"[\1]", text)
    return re.sub(r"\s+", " ", text).strip()


def _citation_markers(sentence: str) -> list[dict[str, str]]:
    markers: list[dict[str, str]] = []
    numeric_spans: list[tuple[int, int]] = []
    for m in NUMERIC_CITE_RE.finditer(sentence):
        markers.append({"type": "numeric", "marker": m.group(0), "value": m.group(1)})
        numeric_spans.append(m.span())
    for m in KEY_CITE_RE.finditer(sentence):
        if any(m.start() >= a and m.end() <= b for a, b in numeric_spans):
            continue
        keys = [k.strip() for k in re.split(r"[,;]", m.group(1)) if k.strip()]
        if keys:
            markers.append({"type": "bibtex_key", "marker": m.group(0), "value": ",".join(keys)})
    for m in AUTHOR_YEAR_RE.finditer(sentence):
        markers.append({"type": "author_year", "marker": m.group(0), "value": m.group(1)})
    for m in TEXTUAL_AUTHOR_YEAR_RE.finditer(sentence):
        markers.append({"type": "textual_author_year", "marker": m.group(0), "value": f"{m.group(1)} {m.group(2)}"})
    return markers


def _anchor_for_line(path: Path, packet: Path, line_no: int) -> str:
    try:
        rel = path.relative_to(packet)
    except Exception:
        rel = Path(path.name)
    return f"{rel}:L{line_no}"


def _claim_strength(sentence: str) -> str:
    lower = sentence.lower()
    if any(v in lower for v in CLAIM_VERBS):
        return "explicit_claim"
    if any(w in lower for w in ["because", "therefore", "thus", "however", "although", "whereas"]):
        return "argumentative_context"
    return "citation_context"



def _title_tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text or "")}


def _load_cited_paper_lookup(packet: Path) -> dict[str, Any]:
    """Load optional cited/prior-work content supplied by the user.

    Supported locations:
    - prior_work_packet.json at packet root
    - prior_work/prior_work_packet.json
    - prior_work/*.json containing entries/prior_work_entries

    Entries may include id/key/title/abstract/raw_excerpt/full_text/text.
    """
    lookup: dict[str, Any] = {"by_id": {}, "by_title_tokens": [], "entry_count": 0}
    candidates = [packet / "prior_work_packet.json", packet / "prior_work" / "prior_work_packet.json"]
    candidates.extend(sorted((packet / "prior_work").glob("*.json")) if (packet / "prior_work").exists() else [])
    seen_paths: set[Path] = set()
    for path in candidates:
        if not path.exists() or path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data if isinstance(data, list) else data.get("prior_work_entries", data.get("entries", [])) if isinstance(data, dict) else []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            eid = str(entry.get("id") or entry.get("key") or entry.get("doi") or "").strip()
            title = str(entry.get("title") or "").strip()
            context = str(entry.get("abstract") or entry.get("raw_excerpt") or entry.get("full_text") or entry.get("text") or "").strip()
            enriched = {**entry, "_support_context": context[:5000]}
            if eid:
                lookup["by_id"][eid] = enriched
            if title:
                lookup["by_title_tokens"].append((title, _title_tokens(title), enriched))
            lookup["entry_count"] += 1
    return lookup


def _match_cited_context(markers: list[dict[str, str]], sentence: str, lookup: dict[str, Any], ref_lookup: dict[str, Any]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for marker in markers:
        if marker["type"] == "bibtex_key":
            for key in [k.strip() for k in marker["value"].split(",") if k.strip()]:
                entry = lookup["by_id"].get(key) or ref_lookup.get("bibtex_keys", {}).get(key)
                if entry:
                    matches.append({"match_type": "bibtex_key", "key": key, "title": entry.get("title", ""), "context_available": bool(entry.get("_support_context") or entry.get("abstract") or entry.get("raw_excerpt"))})
        elif marker["type"] in {"author_year", "textual_author_year"}:
            token_set = _title_tokens(marker["value"] + " " + sentence)
            best: tuple[int, dict[str, Any]] | None = None
            for title, toks, entry in lookup.get("by_title_tokens", []):
                score = len(toks & token_set)
                if score >= 2 and (best is None or score > best[0]):
                    best = (score, entry)
            if best:
                matches.append({"match_type": marker["type"], "title": best[1].get("title", ""), "context_available": bool(best[1].get("_support_context")), "score": best[0]})
    return {"matched_cited_papers": matches[:5], "cited_paper_context_available": any(m.get("context_available") for m in matches)}


def _load_reference_lookup(packet: Path) -> dict[str, Any]:
    lookup: dict[str, Any] = {"numeric": {}, "bibtex_keys": {}, "reference_entries": []}
    pdf_refs = _load_json(packet / "derived" / "pdf" / "citation_reference_manifest.json")
    for entry in pdf_refs.get("reference_entries", []) or []:
        label = str(entry.get("label", "")).strip()
        if label:
            lookup["numeric"][label] = entry
        lookup["reference_entries"].append(entry)
    bib = _load_json(packet / "references" / "bibtex_entries.json")
    for entry in bib.get("entries", []) or []:
        key = str(entry.get("key", "")).strip()
        if key:
            lookup["bibtex_keys"][key] = entry
    return lookup


def _reference_status(markers: list[dict[str, str]], lookup: dict[str, Any]) -> str:
    if not markers:
        return "no_citation_marker"
    statuses: list[str] = []
    for marker in markers:
        if marker["type"] == "numeric":
            nums = re.findall(r"\d+", marker["value"])
            if nums and all(n in lookup["numeric"] for n in nums):
                statuses.append("reference_entry_found")
            else:
                statuses.append("reference_entry_missing_or_unresolved")
        elif marker["type"] == "bibtex_key":
            keys = [k.strip() for k in marker["value"].split(",") if k.strip()]
            if keys and all(k in lookup.get("bibtex_keys", {}) for k in keys):
                statuses.append("reference_entry_found")
            else:
                statuses.append("reference_entry_missing_or_unresolved")
        else:
            # Without cited paper content, author-year support cannot be confirmed.
            statuses.append("requires_verification")
    if "reference_entry_missing_or_unresolved" in statuses:
        return "reference_entry_missing_or_unresolved"
    if all(s == "reference_entry_found" for s in statuses):
        return "reference_entry_found"
    return "requires_verification"


def build_citation_claim_matrix(packet: Path, max_items: int = 250) -> dict[str, Any]:
    packet = Path(packet).resolve()
    lookup = _load_reference_lookup(packet)
    cited_lookup = _load_cited_paper_lookup(packet)
    entries: list[dict[str, Any]] = []
    for path in _packet_text_files(packet):
        try:
            raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line_no, line in enumerate(raw_lines, start=1):
            clean = _clean_line(line)
            if not clean or len(clean) < 20:
                continue
            markers = _citation_markers(clean)
            if not markers:
                continue
            # Treat line as local context; for extracted PDFs it is already line-anchored.
            sentence_candidates = SENTENCE_SPLIT_RE.split(clean)
            selected = max(sentence_candidates, key=lambda s: len(_citation_markers(s))) if sentence_candidates else clean
            markers = _citation_markers(selected) or markers
            cited_match = _match_cited_context(markers, selected, cited_lookup, lookup)
            support_status = "evaluable_with_cited_context" if cited_match.get("cited_paper_context_available") else "requires_verification"
            verification_need = "Use matched cited-paper abstract/full text to assess support." if cited_match.get("cited_paper_context_available") else "Provide the cited paper abstract/full text to determine whether the citation truly supports the claim."
            entries.append({
                "item_id": f"CIT-{len(entries)+1:04d}",
                "claim_or_context": selected[:1000],
                "anchor": _anchor_for_line(path, packet, line_no),
                "citation_markers": markers,
                "claim_context_type": _claim_strength(selected),
                "reference_status": _reference_status(markers, lookup),
                "support_status": support_status,
                "verification_need": verification_need,
                **cited_match,
                "reviewer_notes": "",
            })
            if len(entries) >= max_items:
                break
        if len(entries) >= max_items:
            break
    warnings = []
    if not entries:
        warnings.append("No citation markers were found in packet text. Check whether citation extraction or manuscript text extraction failed.")
    return {
        "version": "v1-citation-claim-matrix",
        "status": "ok" if entries else "no_citation_claims_found",
        "entry_count": len(entries),
        "reference_lookup_summary": {
            "numeric_reference_entries": len(lookup["numeric"]),
            "bibtex_entries": len(lookup["bibtex_keys"]),
            "reference_entry_candidates": len(lookup["reference_entries"]),
            "cited_paper_context_entries": cited_lookup.get("entry_count", 0),
        },
        "entries": entries,
        "warnings": warnings,
    }


def write_citation_claim_matrix(packet: Path, out_dir: Path | None = None, max_items: int = 250) -> dict[str, Any]:
    packet = Path(packet).resolve()
    target_dir = out_dir or (packet / "coverage")
    target_dir.mkdir(parents=True, exist_ok=True)
    matrix = build_citation_claim_matrix(packet, max_items=max_items)
    write_json(target_dir / "citation_claim_matrix.json", matrix)
    lines = [
        "# Citation-Claim Matrix",
        "",
        "This matrix links citation-bearing claim/context sentences to citation markers and available reference candidates. It is a verification scaffold, not proof that citations are correct.",
        "",
        f"Entry count: `{matrix['entry_count']}`",
        "",
        "| ID | Anchor | Citation(s) | Reference status | Context type | Claim/context preview |",
        "|---|---|---|---|---|---|",
    ]
    for item in matrix["entries"]:
        markers = ", ".join(f"`{m['marker']}`" for m in item.get("citation_markers", []))
        preview = str(item.get("claim_or_context", ""))[:220].replace("|", "\\|")
        lines.append(f"| `{item['item_id']}` | `{item['anchor']}` | {markers} | `{item['reference_status']}` | `{item['claim_context_type']}` | {preview} |")
    if matrix["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in matrix["warnings"])
    lines.extend([
        "",
        "## Reviewer instructions",
        "",
        "- Do not mark a citation as unsupported unless cited-paper content is available.",
        "- Use `requires_verification` when only the manuscript citation marker/reference list is available.",
        "- Prioritise citation checks for novelty, related-work, and strong empirical claims.",
    ])
    (target_dir / "citation_claim_matrix.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return matrix
