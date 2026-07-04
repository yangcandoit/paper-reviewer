from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import re

from .io_utils import TEXT_EXTS

CAPTION_KIND_RE = re.compile(r"^(fig\.?|figure|table)\s*([0-9IVXivx]+)", re.I)
MENTION_RE = re.compile(r"\b(fig\.?|figure|table)\s*([0-9IVXivx]+)\b", re.I)
CLAIM_CUE_RE = re.compile(r"\b(show|shows|shown|demonstrate|demonstrates|indicate|indicates|compare|compares|outperform|outperforms|improve|improves|achieve|achieves|confirm|confirms|suggest|suggests)\b", re.I)


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _caption_id(text: str) -> tuple[str, str]:
    m = CAPTION_KIND_RE.search(text.strip())
    if not m:
        return "unknown", ""
    kind = "table" if m.group(1).lower().startswith("table") else "figure"
    return kind, m.group(2)


def _normalise_number(value: str) -> str:
    return value.strip().lower().rstrip(".")


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


def _clean_text(line: str) -> str:
    line = re.sub(r"\b(?:L\d+|P\d+L\d+|[^\s:]+\.pdf:p\d+:L\d+):\s*", "", line)
    line = re.sub(r"\\(?:ref|autoref|cref|Cref)\{([^}]+)\}", r"\1", line)
    return re.sub(r"\s+", " ", line).strip()


def _anchor(path: Path, packet: Path, line_no: int) -> str:
    try:
        rel = path.relative_to(packet)
    except Exception:
        rel = Path(path.name)
    return f"{rel}:L{line_no}"


def _collect_mentions(packet: Path) -> dict[tuple[str, str], list[dict[str, str]]]:
    mentions: dict[tuple[str, str], list[dict[str, str]]] = {}
    for path in _packet_text_files(packet):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line_no, line in enumerate(lines, start=1):
            clean = _clean_text(line)
            if len(clean) < 20:
                continue
            for m in MENTION_RE.finditer(clean):
                kind = "table" if m.group(1).lower().startswith("table") else "figure"
                number = _normalise_number(m.group(2))
                claim_like = bool(CLAIM_CUE_RE.search(clean))
                mentions.setdefault((kind, number), []).append({
                    "anchor": _anchor(path, packet, line_no),
                    "text": clean[:1000],
                    "claim_like": claim_like,
                })
    return mentions


def build_figure_table_matrix(packet: Path) -> dict[str, Any]:
    packet = Path(packet).resolve()
    pdf_root = packet / "derived" / "pdf"
    visual_manifest = _load_json(pdf_root / "visual_manifest.json")
    pdf_manifest = _load_json(pdf_root / "pdf_extraction_manifest.json")
    captions = visual_manifest.get("caption_candidates") or pdf_manifest.get("caption_candidates") or []
    mentions = _collect_mentions(packet)
    entries: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for idx, cap in enumerate(captions, start=1):
        text = str(cap.get("text", ""))
        kind, number = _caption_id(text)
        norm_number = _normalise_number(number)
        key = (kind, norm_number)
        seen_keys.add(key)
        item_mentions = mentions.get(key, []) if kind != "unknown" and norm_number else []
        entries.append({
            "item_id": f"{kind.upper()}-{number or idx}",
            "kind": kind,
            "number": number,
            "caption_anchor": cap.get("anchor", ""),
            "caption_text": text,
            "page_hint": str(cap.get("anchor", "")).split(":L")[0] if cap.get("anchor") else "",
            "textual_mentions": item_mentions[:20],
            "claim_like_mentions": [m for m in item_mentions if m.get("claim_like")][:10],
            "claimed_support": "to be filled by reviewer from textual_mentions and caption",
            "visual_asset": "see derived/pdf/visual_index.md page render for the page_hint",
            "checks": {
                "caption_self_contained": "unknown",
                "axis_or_legend_readable": "unknown",
                "statistical_details_present": "unknown",
                "text_interpretation_matches_visual": "unknown",
                "supports_claim": "unknown",
            },
            "reviewer_notes": "",
        })

    # Add figure/table mentions that lack caption candidates, because these are often extraction gaps.
    for (kind, number), item_mentions in sorted(mentions.items()):
        if (kind, number) in seen_keys:
            continue
        entries.append({
            "item_id": f"{kind.upper()}-{number}",
            "kind": kind,
            "number": number,
            "caption_anchor": "missing_caption_candidate",
            "caption_text": "",
            "page_hint": "unknown",
            "textual_mentions": item_mentions[:20],
            "claim_like_mentions": [m for m in item_mentions if m.get("claim_like")][:10],
            "claimed_support": "to be filled by reviewer from textual_mentions; caption candidate was not extracted",
            "visual_asset": "see page renders manually; caption candidate missing",
            "checks": {
                "caption_self_contained": "unknown",
                "axis_or_legend_readable": "unknown",
                "statistical_details_present": "unknown",
                "text_interpretation_matches_visual": "unknown",
                "supports_claim": "unknown",
            },
            "reviewer_notes": "",
        })

    warnings = []
    if not captions:
        warnings.append("No figure/table caption candidates found. Use page images and manuscript sections manually.")
    missing_caption_count = sum(1 for e in entries if e.get("caption_anchor") == "missing_caption_candidate")
    if missing_caption_count:
        warnings.append(f"{missing_caption_count} figure/table mentions had no extracted caption candidate.")
    return {"status": "ok" if entries else "no_figure_table_candidates", "entry_count": len(entries), "entries": entries, "warnings": warnings}


def write_figure_table_matrix(packet: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report = build_figure_table_matrix(packet)
    target_dir = out_dir or (Path(packet) / "coverage")
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "figure_table_evidence_matrix.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Figure/Table Evidence Matrix",
        "",
        "This matrix links figure/table caption candidates with textual mentions and claim-like sentences. It is a scaffold for visual/figure review, not a substitute for reading the original PDF.",
        "",
        f"Entry count: `{report['entry_count']}`",
        "",
        "| Item | Caption anchor | Mentions | Claim-like mentions | Caption preview | Key checks |",
        "|---|---|---:|---:|---|---|",
    ]
    for entry in report["entries"]:
        preview = str(entry["caption_text"] or "[caption candidate missing]")[:180].replace("|", "\\|")
        lines.append(
            f"| `{entry['item_id']}` | `{entry['caption_anchor']}` | {len(entry.get('textual_mentions', []))} | {len(entry.get('claim_like_mentions', []))} | {preview} | claim support, caption, labels, statistics, interpretation |"
        )
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""] + [f"- {w}" for w in report["warnings"]])
    lines.extend([
        "",
        "## Reviewer instructions",
        "",
        "For each figure/table, verify: what claim it supports, whether the caption is self-contained, whether labels/legends/axes are readable, whether statistical details are sufficient, and whether the manuscript text over-interprets the visual evidence.",
        "Use `textual_mentions` to connect each visual item to the specific manuscript claims that depend on it.",
    ])
    (target_dir / "figure_table_evidence_matrix.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
