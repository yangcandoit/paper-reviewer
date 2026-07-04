from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import re
import shutil
import subprocess
import urllib.parse

ALLOWED_GROBID_HOSTS = {"localhost", "127.0.0.1", "::1"}

LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./\\-])(?:"
    r"/(?:tmp|home|Users)(?:/[^\s\"'<>:;|]+)+"
    r"|[A-Za-z]:\\(?:[^\\\s\"'<>:;|]+\\)*[^\\\s\"'<>:;|]+"
    r")"
)


def redact_local_paths(text: str) -> str:
    """Redact common local absolute paths while preserving surrounding logs."""
    if not text:
        return text
    return LOCAL_PATH_RE.sub("[redacted_path]", text)


def _tail_log(text: str, limit: int = 2000) -> str:
    return redact_local_paths((text or "")[-limit:])

def _write_manifest(out_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "advanced_ingestion_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest

def _base_manifest(pdf_path: Path, engine: str) -> dict[str, Any]:
    return {"source_pdf": Path(pdf_path).name, "engine": engine, "status": "not_run", "outputs": [], "warnings": [], "notes": "Advanced engines are optional. The core skill remains usable with the simple PyMuPDF pipeline."}

def run_docling(pdf_path: Path, out_dir: Path) -> dict[str, Any]:
    manifest = _base_manifest(pdf_path, "docling")
    exe = shutil.which("docling")
    if not exe:
        manifest["status"] = "missing_tool"
        manifest["warnings"].append("docling CLI not found. Install and run it outside the core skill, or use the simple PDF pipeline.")
        return _write_manifest(out_dir, manifest)
    target = out_dir / "docling"; target.mkdir(parents=True, exist_ok=True)
    cmd = [exe, str(Path(pdf_path).resolve()), "--to", "md", "--output", str(target)]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=600, check=False)
        manifest.update({"status": "ok" if proc.returncode == 0 else "failed", "returncode": proc.returncode, "stdout_tail": _tail_log(proc.stdout), "stderr_tail": _tail_log(proc.stderr), "outputs": [str(p.relative_to(out_dir)) for p in target.rglob("*") if p.is_file()]})
    except Exception as exc:
        manifest["status"] = "failed"; manifest["warnings"].append(redact_local_paths(str(exc)))
    return _write_manifest(out_dir, manifest)

def run_marker(pdf_path: Path, out_dir: Path) -> dict[str, Any]:
    manifest = _base_manifest(pdf_path, "marker")
    exe = shutil.which("marker_single") or shutil.which("marker")
    if not exe:
        manifest["status"] = "missing_tool"; manifest["warnings"].append("Marker CLI not found. Install optional marker tooling outside the core skill, or use simple PDF pipeline.")
        return _write_manifest(out_dir, manifest)
    target = out_dir / "marker"; target.mkdir(parents=True, exist_ok=True)
    cmd = [exe, str(Path(pdf_path).resolve()), str(target)]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=900, check=False)
        manifest.update({"status": "ok" if proc.returncode == 0 else "failed", "returncode": proc.returncode, "stdout_tail": _tail_log(proc.stdout), "stderr_tail": _tail_log(proc.stderr), "outputs": [str(p.relative_to(out_dir)) for p in target.rglob("*") if p.is_file()]})
    except Exception as exc:
        manifest["status"] = "failed"; manifest["warnings"].append(redact_local_paths(str(exc)))
    return _write_manifest(out_dir, manifest)

def run_grobid(pdf_path: Path, out_dir: Path, endpoint: str = "http://localhost:8070") -> dict[str, Any]:
    manifest = _base_manifest(pdf_path, "grobid")
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_GROBID_HOSTS:
        manifest["status"] = "rejected_endpoint"; manifest["warnings"].append("GROBID endpoint must be localhost/127.0.0.1/::1 to avoid accidental manuscript upload or SSRF.")
        return _write_manifest(out_dir, manifest)
    import urllib.request
    boundary = "----psairgrobidboundary"
    pdf_bytes = Path(pdf_path).read_bytes()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="input"; filename="paper.pdf"\r\n',
        b"Content-Type: application/pdf\r\n\r\n",
        pdf_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    url = endpoint.rstrip("/") + "/api/processFulltextDocument"
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    target = out_dir / "grobid"
    target.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            tei = resp.read()
        if not tei.strip():
            manifest["status"] = "failed"
            manifest["warnings"].append("GROBID returned an empty response.")
        else:
            out_file = target / "fulltext.tei.xml"
            out_file.write_bytes(tei)
            manifest.update({"status": "ok", "outputs": [str(out_file.relative_to(out_dir))]})
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["warnings"].append(redact_local_paths(f"Local GROBID request failed: {exc}"))
    return _write_manifest(out_dir, manifest)


def run_auto_advanced_ingestion(pdf_path: Path, out_dir: Path, *, grobid_endpoint: str = "http://localhost:8070") -> dict[str, Any]:
    """Run the best available optional local advanced engine without making it a core dependency.

    Preference order:
    1. Marker if installed, because it produces LLM-ready Markdown/JSON.
    2. Docling if installed, because it provides stronger layout/table-oriented conversion.
    3. Local GROBID if reachable, for TEI/reference enrichment.

    If none are available, write a manifest explaining that the simple PyMuPDF pipeline remains the active source.
    """
    manifest = _base_manifest(pdf_path, "auto")
    out_dir.mkdir(parents=True, exist_ok=True)
    attempted: list[dict[str, Any]] = []
    if shutil.which("marker_single") or shutil.which("marker"):
        result = run_marker(pdf_path, out_dir)
        attempted.append(result)
        manifest.update({"status": result.get("status"), "selected_engine": "marker", "outputs": result.get("outputs", []), "attempted": attempted})
        return _write_manifest(out_dir, manifest)
    if shutil.which("docling"):
        result = run_docling(pdf_path, out_dir)
        attempted.append(result)
        manifest.update({"status": result.get("status"), "selected_engine": "docling", "outputs": result.get("outputs", []), "attempted": attempted})
        return _write_manifest(out_dir, manifest)
    # GROBID is useful but should remain localhost-only. Try only if explicitly available.
    try:
        result = run_grobid(pdf_path, out_dir, endpoint=grobid_endpoint)
        attempted.append(result)
        if result.get("status") == "ok":
            manifest.update({"status": "ok", "selected_engine": "grobid", "outputs": result.get("outputs", []), "attempted": attempted})
            return _write_manifest(out_dir, manifest)
    except Exception:
        pass
    manifest["status"] = "no_optional_engine_available"
    manifest["selected_engine"] = "simple"
    manifest["attempted"] = attempted
    manifest["warnings"].append("No optional advanced PDF engine was available. The simple PyMuPDF text/visual pipeline remains the active ingestion path.")
    return _write_manifest(out_dir, manifest)


def run_advanced_ingestion(pdf_path: Path, out_dir: Path, engine: str, *, grobid_endpoint: str = "http://localhost:8070") -> dict[str, Any]:
    engine = engine.lower().strip()
    if engine == "auto": return run_auto_advanced_ingestion(pdf_path, out_dir, grobid_endpoint=grobid_endpoint)
    if engine == "docling": return run_docling(pdf_path, out_dir)
    if engine == "marker": return run_marker(pdf_path, out_dir)
    if engine == "grobid": return run_grobid(pdf_path, out_dir, endpoint=grobid_endpoint)
    manifest = _base_manifest(pdf_path, engine); manifest["status"] = "unknown_engine"; manifest["warnings"].append("Supported optional engines: docling, marker, grobid.")
    return _write_manifest(out_dir, manifest)
