from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import struct

from .figure_table import build_figure_table_matrix
from .io_utils import write_json


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        data = path.read_bytes()[:32]
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if data.startswith(b"\xff\xd8"):
            raw = path.read_bytes()
            i = 2
            while i + 9 < len(raw):
                if raw[i] != 0xFF:
                    i += 1
                    continue
                marker = raw[i + 1]
                length = int.from_bytes(raw[i + 2:i + 4], "big")
                if marker in {0xC0, 0xC2}:
                    h = int.from_bytes(raw[i + 5:i + 7], "big")
                    w = int.from_bytes(raw[i + 7:i + 9], "big")
                    return w, h
                i += 2 + max(length, 1)
    except Exception:
        pass
    return None, None


def _visual_assets(packet: Path) -> list[dict[str, Any]]:
    roots = [packet / "derived" / "pdf" / "page_images", packet / "derived" / "pdf" / "embedded_images"]
    assets: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*")):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or not path.is_file():
                continue
            w, h = _image_size(path)
            try:
                rel = str(path.relative_to(packet))
            except Exception:
                rel = path.name
            assets.append({"path": rel, "width": w, "height": h, "bytes": path.stat().st_size})
    return assets


def build_visual_claim_audit(packet: Path) -> dict[str, Any]:
    packet = Path(packet).resolve()
    matrix_path = packet / "coverage" / "figure_table_evidence_matrix.json"
    matrix = _load_json(matrix_path) or build_figure_table_matrix(packet)
    assets = _visual_assets(packet)
    entries: list[dict[str, Any]] = []
    low_resolution = any((a.get("width") or 9999) < 800 or (a.get("height") or 9999) < 600 for a in assets)
    for item in matrix.get("entries", []):
        flags: list[str] = []
        if item.get("caption_anchor") == "missing_caption_candidate":
            flags.append("missing_visual_evidence")
        if item.get("claim_like_mentions") and not assets:
            flags.append("missing_visual_evidence")
        if low_resolution:
            flags.append("low_visual_confidence")
        checks = item.get("checks") or {}
        if checks.get("axis_or_legend_readable") == "no":
            flags.append("axis_labels_unreadable")
        if checks.get("text_interpretation_matches_visual") == "no":
            flags.append("visual_text_mismatch")
        if item.get("kind") == "table" and not item.get("caption_text"):
            flags.append("source_table_requested")
        confidence = "low" if flags else "medium"
        entries.append({
            "item_id": item.get("item_id"),
            "kind": item.get("kind"),
            "caption_anchor": item.get("caption_anchor"),
            "claim_like_mention_count": len(item.get("claim_like_mentions") or []),
            "flags": sorted(set(flags)),
            "visual_confidence": confidence,
            "required_guardrails": [
                "Do not infer metrics from unreadable axes or legends.",
                "Do not invent numeric values if they are not readable.",
                "Request source table or LaTeX when rendered tables are unreadable.",
            ] if flags else ["Verify against the original PDF or source assets before making visual-evidence claims."],
        })
    if not entries and not assets:
        entries.append({
            "item_id": "VISUAL-AUDIT-001",
            "kind": "packet",
            "caption_anchor": "information_gap",
            "claim_like_mention_count": 0,
            "flags": ["missing_visual_evidence"],
            "visual_confidence": "low",
            "required_guardrails": ["No extracted visual assets or figure/table candidates were found; do not make visual claims without the source PDF/assets."],
        })
    return {
        "version": "v1-pre2-visual-claim-audit",
        "status": "ok" if entries else "no_visual_claims_detected",
        "asset_count": len(assets),
        "assets": assets[:200],
        "entry_count": len(entries),
        "entries": entries,
        "policy": {
            "unreadable_axes": "do_not_infer_metric",
            "unreadable_numbers": "do_not_invent_values",
            "low_resolution": "mark_low_visual_confidence",
            "caption_visual_mismatch": "mark_visual_text_mismatch",
            "unreadable_table": "request_source_table_or_latex",
            "missing_referenced_visual": "mark_missing_visual_evidence",
        },
    }


def write_visual_claim_audit(packet: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report = build_visual_claim_audit(packet)
    target = Path(out_dir) if out_dir else Path(packet) / "coverage"
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "visual_confidence_manifest.json", report)
    lines = [
        "# Visual Claim Audit",
        "",
        "This guard prevents visual reviewers from inferring details that are not readable or not present in the local visual bundle.",
        "",
        f"Asset count: `{report['asset_count']}`",
        f"Entry count: `{report['entry_count']}`",
        "",
        "| Item | Confidence | Flags | Guardrail |",
        "|---|---|---|---|",
    ]
    for item in report["entries"]:
        flags = ", ".join(item.get("flags") or ["none"])
        guard = "; ".join(item.get("required_guardrails") or [])[:260].replace("|", "\\|")
        lines.append(f"| `{item.get('item_id')}` | {item.get('visual_confidence')} | {flags} | {guard} |")
    (target / "visual_claim_audit.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
