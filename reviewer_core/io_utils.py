from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
from typing import Any

TEXT_EXTS = {".md", ".txt", ".tex", ".rst", ".bib", ".csv", ".tsv", ".json", ".yaml", ".yml"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path, max_chars: int | None = None) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + f"\n\n[TRUNCATED after {max_chars} characters]"
    return text


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(value: str, default: str = "item") -> str:
    value = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or default


def line_anchor(path: Path, start: int, end: int | None = None) -> str:
    if end is None or end == start:
        return f"{path.name}:L{start}"
    return f"{path.name}:L{start}-L{end}"


def with_line_numbers(text: str, start_line: int = 1) -> str:
    return "\n".join(f"L{i}: {line}" for i, line in enumerate(text.splitlines(), start_line))
