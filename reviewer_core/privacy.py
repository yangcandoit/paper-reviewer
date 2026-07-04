from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import re

from .io_utils import TEXT_EXTS, read_text, write_json

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
SENSITIVE_NAME_RE = re.compile(r"(^|/)(\.env(?:\..*)?|id_rsa|id_dsa|id_ecdsa|id_ed25519|[^/]+\.(?:pem|key))$", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LOCAL_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._ -]+){2,}|[A-Za-z]:\\(?:[^\\\s]+\\){1,}[^\\\s]+")
TOKEN_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|[A-Za-z0-9_=-]{32,}\.[A-Za-z0-9_=-]{10,}\.[A-Za-z0-9_=-]{10,})\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|OPENSSH PRIVATE KEY", re.I)
AUTHOR_RE = re.compile(r"\\author\{|\b(author|affiliation|department|university|institute|laboratory)\b", re.I)
SUPP_RE = re.compile(r"\b(supplement|supplementary|appendix|additional file)\b", re.I)
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return path.name


def _is_sensitive_named(path: Path, packet: Path) -> bool:
    rel = _rel(path, packet).replace("\\", "/")
    return bool(SENSITIVE_NAME_RE.search(rel))


def _packet_files(packet: Path) -> list[Path]:
    """Return packet files that could be considered for provider context.

    Hidden files are intentionally not skipped: a user may accidentally place a
    packet-local `.env` or SSH-key-like file in the packet, and the preview must
    be able to flag that before any remote provider run. Cache and VCS folders
    are skipped because they are not part of the manuscript packet contract.
    """
    packet = Path(packet).resolve()
    files: list[Path] = []
    for p in sorted(packet.rglob("*")):
        if not p.is_file():
            continue
        try:
            rel_parts = p.relative_to(packet).parts
        except Exception:
            rel_parts = p.parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        files.append(p)
    return files


def _is_text_like_for_preview(path: Path, packet: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTS or _is_sensitive_named(path, packet)


def preview_provider_payload(packet: Path, max_file_chars: int = 200000) -> dict[str, Any]:
    packet = Path(packet).resolve()
    files = _packet_files(packet)
    text_files = [p for p in files if _is_text_like_for_preview(p, packet)]
    images = [p for p in files if p.suffix.lower() in IMAGE_EXTS]
    send_images = _truthy(os.environ.get("AI_REVIEWER_SEND_IMAGES"))
    total_chars = 0
    detections = {
        "author_names_or_affiliations_appear": False,
        "local_paths_appear": False,
        "email_addresses_appear": False,
        "token_like_strings_appear": False,
        "env_or_ssh_key_like_strings_appear": False,
        "supplementary_files_included": False,
    }
    examples: dict[str, list[str]] = {k: [] for k in detections}
    for path in text_files:
        rel = _rel(path, packet)
        if SUPP_RE.search(rel):
            detections["supplementary_files_included"] = True
            if len(examples["supplementary_files_included"]) < 5:
                examples["supplementary_files_included"].append(rel)
        if _is_sensitive_named(path, packet):
            detections["env_or_ssh_key_like_strings_appear"] = True
            if len(examples["env_or_ssh_key_like_strings_appear"]) < 5:
                examples["env_or_ssh_key_like_strings_appear"].append(rel)
        try:
            text = read_text(path, max_chars=max_file_chars)
        except Exception:
            continue
        total_chars += len(text)
        checks = [
            ("author_names_or_affiliations_appear", AUTHOR_RE),
            ("local_paths_appear", LOCAL_PATH_RE),
            ("email_addresses_appear", EMAIL_RE),
            ("token_like_strings_appear", TOKEN_RE),
            ("env_or_ssh_key_like_strings_appear", PRIVATE_KEY_RE),
        ]
        for key, pattern in checks:
            if pattern.search(text):
                detections[key] = True
                if len(examples[key]) < 5 and rel not in examples[key]:
                    examples[key].append(rel)
    image_count = len(images)
    risk_flags = [k for k, v in detections.items() if v]
    if send_images and image_count:
        risk_flags.append("page_or_figure_images_will_be_sent")
    return {
        "version": "v1-pre2-provider-payload-preview",
        "packet": packet.name,
        "text_file_count": len(text_files),
        "estimated_text_size_chars": total_chars,
        "estimated_text_size_bytes_utf8": total_chars,
        "page_images_will_be_sent": bool(send_images and image_count),
        "image_count": image_count,
        "image_sending_env": "AI_REVIEWER_SEND_IMAGES=1" if send_images else "off_by_default",
        "supplementary_files_included": detections["supplementary_files_included"],
        **detections,
        "risk_flags": risk_flags,
        "examples_by_flag": examples,
        "privacy_note": "Preview only. No provider call was made and no manuscript content was sent.",
    }


def write_provider_payload_preview(packet: Path, out_dir: Path | None = None) -> dict[str, Any]:
    report = preview_provider_payload(packet)
    target = Path(out_dir) if out_dir else Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "privacy_risk_report.json", report)
    lines = [
        "# Provider Payload Preview",
        "",
        "No provider call was made. This report estimates what a remote model workflow could receive if run with the current packet and environment.",
        "",
        f"Text files included: `{report['text_file_count']}`",
        f"Estimated text size: `{report['estimated_text_size_chars']}` characters",
        f"Images present: `{report['image_count']}`",
        f"Images will be sent: `{report['page_images_will_be_sent']}`",
        f"Image setting: `{report['image_sending_env']}`",
        "",
        "## Privacy flags",
        "",
        "| Flag | Detected | Example files |",
        "|---|---:|---|",
    ]
    keys = [
        "author_names_or_affiliations_appear", "local_paths_appear", "email_addresses_appear",
        "token_like_strings_appear", "env_or_ssh_key_like_strings_appear", "supplementary_files_included",
    ]
    for key in keys:
        examples = ", ".join(report["examples_by_flag"].get(key) or [])
        lines.append(f"| {key} | {report[key]} | {examples} |")
    if report["page_images_will_be_sent"]:
        lines.extend(["", "**Warning:** `AI_REVIEWER_SEND_IMAGES=1` is enabled, so visual assets may be sent by compatible provider runs."])
    (target / "provider_payload_preview.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report
