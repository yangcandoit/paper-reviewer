from __future__ import annotations

from pathlib import Path
from typing import Any
import datetime as dt
import json
import re

from .io_utils import write_json


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _evidence_level(entry: dict[str, Any]) -> str:
    if entry.get("full_text") or entry.get("text") or entry.get("pdf_text"):
        return "full_text"
    if entry.get("abstract"):
        return "abstract"
    if entry.get("user_note") or entry.get("note") or entry.get("notes"):
        return "user_note"
    return "metadata_only"


def _source(path: Path, entry: dict[str, Any]) -> str:
    raw = str(entry.get("source") or "").lower()
    if raw in {"user_provided", "openalex", "crossref", "local", "manual"}:
        return raw
    name = path.name.lower()
    if "openalex" in name:
        return "openalex"
    if "crossref" in name:
        return "crossref"
    if "local" in name:
        return "local"
    if "manual" in name or "user" in name:
        return "manual"
    return "user_provided" if path.suffix.lower() in {".bib", ".md", ".txt"} else "manual"


def _iter_entries(packet: Path) -> list[tuple[Path, dict[str, Any]]]:
    prior = packet / "prior_work"
    refs = packet / "references"
    candidates = []
    if prior.exists():
        candidates.extend(sorted(prior.glob("*.json")))
    if refs.exists():
        candidates.extend(sorted(refs.glob("bibtex_entries.json")))
    out: list[tuple[Path, dict[str, Any]]] = []
    for path in candidates:
        data = _load_json(path)
        if not data:
            continue
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("prior_work_entries") or data.get("entries") or data.get("results") or []
            if path.name == "query_plan.json":
                for idx, query in enumerate(data.get("queries") or [], start=1):
                    if isinstance(query, dict):
                        out.append((path, {"id": f"query-{idx}", "title": query.get("query", ""), "query": query.get("query", ""), "source": "manual", "evidence_level": "metadata_only"}))
                continue
        else:
            entries = []
        for entry in entries:
            if isinstance(entry, dict):
                out.append((path, entry))
    return out


def build_retrieval_provenance(packet: Path) -> dict[str, Any]:
    packet = Path(packet).resolve()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    items: list[dict[str, Any]] = []
    for idx, (path, entry) in enumerate(_iter_entries(packet), start=1):
        ev = str(entry.get("evidence_level") or _evidence_level(entry))
        confidence = "high" if ev == "full_text" else "medium" if ev in {"abstract", "user_note"} else "low"
        requires_verification = ev in {"metadata_only", "abstract", "user_note"}
        item = {
            "id": str(entry.get("id") or entry.get("key") or entry.get("doi") or f"PW-{idx:03d}"),
            "source": _source(path, entry),
            "query": str(entry.get("query") or entry.get("search_query") or ""),
            "retrieved_at": str(entry.get("retrieved_at") or now),
            "title": str(entry.get("title") or ""),
            "doi": str(entry.get("doi") or ""),
            "url": str(entry.get("url") or entry.get("landing_page_url") or ""),
            "evidence_level": ev if ev in {"metadata_only", "abstract", "full_text", "user_note"} else "metadata_only",
            "used_by": entry.get("used_by") if isinstance(entry.get("used_by"), list) else [],
            "confidence": confidence,
            "requires_verification": requires_verification,
            "provenance_file": str(path.relative_to(packet)) if path.is_relative_to(packet) else path.name,
        }
        items.append(item)
    counts: dict[str, int] = {}
    for item in items:
        counts[item["evidence_level"]] = counts.get(item["evidence_level"], 0) + 1
    return {
        "version": "v1-pre2-retrieval-provenance",
        "policy": "Metadata-only and abstract-level hits must not be treated as proof of novelty or claim support.",
        "item_count": len(items),
        "evidence_level_counts": counts,
        "items": items,
    }


def write_retrieval_provenance(packet: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report = build_retrieval_provenance(packet)
    target = Path(out_dir) if out_dir else Path(packet) / "prior_work"
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "retrieval_provenance.json", report)
    lines = [
        "# Retrieval Provenance Report",
        "",
        "Retrieved or user-provided prior work is evidence with provenance, not ground truth. Metadata-only hits require verification before being used for novelty or citation-claim conclusions.",
        "",
        f"Item count: `{report['item_count']}`",
        "",
        "| ID | Source | Evidence level | Confidence | Requires verification | Title/query |",
        "|---|---|---|---|---:|---|",
    ]
    for item in report["items"]:
        title = (item.get("title") or item.get("query") or "[untitled]")[:180].replace("|", "\\|")
        lines.append(f"| `{item['id']}` | {item['source']} | {item['evidence_level']} | {item['confidence']} | {item['requires_verification']} | {title} |")
    (target / "retrieval_provenance_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
