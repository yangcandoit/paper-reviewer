from __future__ import annotations

"""Best-effort legacy Word (``.doc``) text extraction.

``.doc`` is the legacy OLE2 Compound File Binary format, which is far harder to
read than the zipped-XML ``.docx``. There is no perfect stdlib path, so this
module uses a tiered strategy and always degrades gracefully (it never raises):

1. External text converter, if present on PATH: ``antiword`` or ``catdoc``. These
   are purpose-built, safe (no macro execution) ``.doc`` text extractors and give
   the best fidelity.
2. ``olefile`` (optional ``pip install olefile``), if importable: read the
   ``WordDocument`` OLE stream and reassemble the main text, including fast-saved
   (``fComplex``) documents via the MS-DOC piece table (Plcfpcd) in the Table stream.
3. Pure-standard-library salvage: recover printable text runs directly from the
   raw bytes (both UTF-16LE and CP1252), pick the higher-signal decoding. Low
   fidelity, but dependency-free and enough to make a ``.doc`` reviewable.
4. If nothing yields usable text, report ``missing_capability`` with guidance to
   re-save as ``.docx`` (which this skill extracts natively).

Manuscript files are untrusted: converters are text-only (no LibreOffice/macro
execution), subprocesses run with a timeout, and the salvage path only reads
bytes. The output mirrors ``docx_simple`` so downstream review is uniform.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

# A "printable run" for salvage: letters/digits/space and common punctuation.
_PRINTABLE_RUN = re.compile(r"[\x20-\x7e\u00a0-\u024f]{4,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_DOC_BYTES = 64 * 1024 * 1024  # 64 MB safety cap


def _normalise(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _quality_label(*, status: str, total_chars: int, alpha_ratio: float) -> str:
    if status != "ok":
        return "failed"
    if total_chars < 200 or alpha_ratio < 0.35:
        return "weak"
    if total_chars < 2000:
        return "usable"
    return "good"


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    alpha = sum(1 for c in text if c.isalpha() or c.isspace())
    return alpha / len(text)


def _converter_text(doc_path: Path) -> tuple[str, str] | None:
    """Extract text via antiword/catdoc if available. Returns (text, method)."""
    for tool, args in (("antiword", ["-w", "0"]), ("catdoc", ["-w"])):
        exe = shutil.which(tool)
        if not exe:
            continue
        try:
            proc = subprocess.run(
                [exe, *args, str(doc_path)],
                capture_output=True,
                timeout=60,
                check=False,
            )
        except Exception:
            continue
        if proc.returncode == 0 and proc.stdout:
            text = proc.stdout.decode("utf-8", errors="replace")
            if text.strip():
                return text, f"{tool}"
    return None


def _olefile_text(doc_path: Path) -> tuple[str, str] | None:
    """Extract WordDocument text via olefile, handling simple and fast-saved docs.

    Non-complex documents use the FIB ``fcMin..fcMac`` range. Fast-saved (``fComplex``)
    documents store their text as a piece table in the Table stream; this implements
    the MS-DOC Plcfpcd algorithm to reassemble the pieces (CP1252 for compressed
    pieces, UTF-16LE otherwise). Any failure returns ``None`` so the caller can fall
    back to byte salvage.
    """
    try:
        import olefile  # type: ignore
    except Exception:
        return None
    import struct

    try:
        if not olefile.isOleFile(str(doc_path)):
            return None
        ole = olefile.OleFileIO(str(doc_path))
        try:
            if not ole.exists("WordDocument"):
                return None
            wd = ole.openstream("WordDocument").read()
            flags = struct.unpack_from("<H", wd, 0x0A)[0]
            complex_fast_saved = bool(flags & 0x0004)
            table_name = "1Table" if (flags & 0x0200) else "0Table"
            table_bytes = b""
            if ole.exists(table_name):
                table_bytes = ole.openstream(table_name).read()
        finally:
            ole.close()
    except Exception:
        return None

    if len(wd) < 0x02000 // 512:  # sanity: need at least the FIB
        pass

    # --- Simple (non-complex) documents: contiguous main text range. ---
    if not complex_fast_saved:
        try:
            fc_min = struct.unpack_from("<i", wd, 0x18)[0]
            fc_mac = struct.unpack_from("<i", wd, 0x1C)[0]
        except Exception:
            return None
        if not (0 <= fc_min < fc_mac <= len(wd)):
            return None
        text = _clean_doc_text(wd[fc_min:fc_mac].decode("cp1252", errors="replace"))
        return (text, "olefile-fib") if text.strip() else None

    # --- Fast-saved documents: reassemble via the piece table (Plcfpcd). ---
    try:
        fc_clx = struct.unpack_from("<i", wd, 0x01A2)[0]
        lcb_clx = struct.unpack_from("<i", wd, 0x01A6)[0]
        if not table_bytes or fc_clx < 0 or lcb_clx <= 0 or fc_clx + lcb_clx > len(table_bytes):
            return None
        clx = table_bytes[fc_clx:fc_clx + lcb_clx]

        # Skip any leading Prc structures (0x01, cbGrpprl:u16, data) to reach the
        # Pcdt (0x02, lcb:u32, Plcfpcd).
        i = 0
        while i < len(clx) and clx[i] == 0x01:
            cb = struct.unpack_from("<H", clx, i + 1)[0]
            i += 3 + cb
        if i >= len(clx) or clx[i] != 0x02:
            return None
        lcb_pcd = struct.unpack_from("<I", clx, i + 1)[0]
        pcd = clx[i + 5:i + 5 + lcb_pcd]
        if len(pcd) < 4 or (lcb_pcd - 4) % 12 != 0:
            return None
        n_pieces = (lcb_pcd - 4) // 12
        cps = [struct.unpack_from("<I", pcd, 4 * k)[0] for k in range(n_pieces + 1)]
        pcd_base = 4 * (n_pieces + 1)

        parts: list[str] = []
        for k in range(n_pieces):
            entry = pcd_base + 8 * k
            fc_field = struct.unpack_from("<I", pcd, entry + 2)[0]
            compressed = bool(fc_field & 0x40000000)
            fc_value = fc_field & 0x3FFFFFFF
            cch = cps[k + 1] - cps[k]
            if cch <= 0:
                continue
            if compressed:
                off = fc_value // 2
                parts.append(wd[off:off + cch].decode("cp1252", errors="replace"))
            else:
                off = fc_value
                parts.append(wd[off:off + cch * 2].decode("utf-16-le", errors="replace"))
        text = _clean_doc_text("".join(parts))
        return (text, "olefile-piecetable") if text.strip() else None
    except Exception:
        return None


def _clean_doc_text(text: str) -> str:
    # Map common Word control characters to whitespace/paragraph breaks.
    text = text.replace("\r", "\n").replace("\x07", " ").replace("\x0b", "\n")
    text = text.replace("\x13", "").replace("\x14", "").replace("\x15", "")  # field codes
    text = _CONTROL.sub("", text)
    return text


def _salvage_text(raw: bytes) -> str:
    """Recover printable text runs from raw bytes; try UTF-16LE and CP1252."""
    candidates: list[str] = []
    try:
        utf16 = raw.decode("utf-16-le", errors="ignore")
        candidates.append(utf16)
    except Exception:
        pass
    candidates.append(raw.decode("cp1252", errors="ignore"))

    best = ""
    best_score = -1.0
    for decoded in candidates:
        decoded = _clean_doc_text(decoded)
        runs = [_normalise(m.group(0)) for m in _PRINTABLE_RUN.finditer(decoded)]
        # Keep runs that look like prose (contain a space or are reasonably long).
        runs = [r for r in runs if r and (" " in r or len(r) >= 8)]
        joined = "\n".join(runs)
        score = len(joined) * _alpha_ratio(joined)
        if score > best_score:
            best_score = score
            best = joined
    return best


def extract_doc_to_markdown(doc_path: Path, out_root: Path) -> dict[str, Any]:
    """Extract a legacy ``.doc`` into anchored Markdown, best-effort.

    Returns a manifest with status/quality/method/warnings. Never raises; on total
    failure it records guidance to re-save the file as ``.docx``.
    """
    doc_path = Path(doc_path).resolve()
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "source_doc": doc_path.name,
        "method": "none",
        "status": "not_run",
        "extraction_quality": "failed",
        "paragraph_count": 0,
        "warnings": [],
    }

    try:
        size = doc_path.stat().st_size
    except OSError as exc:
        manifest["status"] = "failed"
        manifest["warnings"].append(f"Could not stat .doc file: {exc}")
        (out_root / "doc_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest
    if size > _MAX_DOC_BYTES:
        manifest["status"] = "failed"
        manifest["warnings"].append("Legacy .doc exceeds the safety size cap; skipped.")
        (out_root / "doc_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    text = ""
    method = "none"
    quality_hint = ""

    result = _converter_text(doc_path)
    if result:
        text, method = result
    if not text:
        result = _olefile_text(doc_path)
        if result:
            text, method = result
    if not text:
        try:
            raw = doc_path.read_bytes()
        except OSError as exc:
            raw = b""
            manifest["warnings"].append(f"Could not read .doc bytes: {exc}")
        salvaged = _salvage_text(raw) if raw else ""
        if salvaged:
            text, method = salvaged, "stdlib-byte-salvage"
            quality_hint = "low-fidelity"
            manifest["warnings"].append(
                "Extracted with a dependency-free byte-salvage fallback: text may be "
                "incomplete or out of order. For higher fidelity install 'antiword' or "
                "'olefile' (pip install olefile), or re-save the file as .docx."
            )

    text = (text or "").strip()
    if not text:
        manifest["status"] = "missing_capability"
        manifest["warnings"].append(
            "Could not extract text from this legacy .doc. Install 'antiword' or "
            "'olefile', or re-save the manuscript as .docx (natively supported)."
        )
        (out_root / "doc_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    # Split into paragraph-like blocks on blank lines / newlines and emit anchors.
    blocks = [ _normalise(b) for b in re.split(r"\n{1,}", text) ]
    blocks = [b for b in blocks if b]
    md_lines = [
        f"# Extracted Legacy Word (.doc) Text: {doc_path.name}",
        "",
        f"Extraction method: `{method}`"
        + (f" ({quality_hint})" if quality_hint else "")
        + ". Prefer LaTeX/Markdown/.docx source when available.",
        "",
        "```text",
    ]
    total_chars = 0
    for idx, block in enumerate(blocks, start=1):
        total_chars += len(block)
        md_lines.append(f"PARA{idx}: {block}")
    md_lines.extend(["```", ""])
    (out_root / "extracted_doc.md").write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    manifest["status"] = "ok"
    manifest["method"] = method
    manifest["paragraph_count"] = len(blocks)
    manifest["total_text_chars"] = total_chars
    manifest["extraction_quality"] = _quality_label(
        status="ok", total_chars=total_chars, alpha_ratio=_alpha_ratio(text)
    )
    if manifest["extraction_quality"] in {"weak", "usable"}:
        manifest["warnings"].append(
            f"Extraction quality is {manifest['extraction_quality']}; verify against the "
            "original document or provide a .docx/LaTeX/Markdown source."
        )
    (out_root / "doc_extraction_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
