from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
from collections import Counter
from typing import Any

from .io_utils import read_text, write_json, TEXT_EXTS

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "has", "have", "in", "into",
    "is", "it", "its", "of", "on", "or", "our", "paper", "study", "that", "the", "their", "this", "to", "towards",
    "toward", "using", "via", "we", "with", "without", "within", "based", "approach", "method", "methods",
    "results", "analysis", "system", "systems", "model", "models", "data", "dataset", "datasets", "new", "novel",
}

TITLE_PATTERNS = [
    re.compile(r"^\\title\{(?P<title>.+?)\}", re.S | re.M),
    re.compile(r"^#\s+(?P<title>.+?)\s*$", re.M),
]
ABSTRACT_PATTERNS = [
    re.compile(r"\\begin\{abstract\}(?P<abstract>.+?)\\end\{abstract\}", re.S | re.I),
    re.compile(r"(?im)^abstract\s*$\s*(?P<abstract>.+?)(?=\n\s*(?:keywords?|1\.?\s+introduction|introduction|related work|background)\s*$|\Z)", re.S),
    re.compile(r"(?im)^#\s*abstract\s*$\s*(?P<abstract>.+?)(?=\n#\s+|\Z)", re.S),
]
KEYWORD_PATTERNS = [
    re.compile(r"(?im)^keywords?\s*[:—-]\s*(?P<keywords>.+)$"),
    re.compile(r"\\keywords\{(?P<keywords>.+?)\}", re.S | re.I),
]


def _clean_latex(text: str) -> str:
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(?:[a-zA-Z]+)(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = text.replace("~", " ")
    return re.sub(r"\s+", " ", text).strip()


def _strip_anchors(text: str) -> str:
    text = re.sub(r"\bP\d+L\d+:\s*", "", text)
    text = re.sub(r"\b[^\s:]+\.pdf:p\d+:L\d+:\s*", "", text)
    text = re.sub(r"\bL\d+:\s*", "", text)
    return text


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_anchors(_clean_latex(text))).strip()


def _read_packet_text(packet_dir: Path, max_chars: int = 60000) -> str:
    packet_dir = packet_dir.resolve()
    priority_patterns = [
        "derived/resolved_manuscript.tex",
        "derived/pdf/extracted_pdf.md",
        "sections/**/*.md",
        "sections/**/*.txt",
        "sections/**/*.tex",
        "derived/sections/*.md",
    ]
    chunks: list[str] = []
    total = 0
    seen: set[Path] = set()
    for pattern in priority_patterns:
        for path in sorted(packet_dir.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            if path.suffix.lower() not in TEXT_EXTS.union({".json"}):
                continue
            seen.add(path)
            try:
                text = read_text(path, max_chars=min(20000, max_chars - total))
            except Exception:
                continue
            chunks.append(text)
            total += len(text)
            if total >= max_chars:
                return "\n".join(chunks)[:max_chars]
    return "\n".join(chunks)[:max_chars]


def extract_metadata_from_text(text: str) -> dict[str, Any]:
    raw = text[:80000]
    title = ""
    abstract = ""
    keywords: list[str] = []

    for pat in TITLE_PATTERNS:
        m = pat.search(raw)
        if m:
            title = _normalise(m.group("title"))
            break
    if not title:
        for line in raw.splitlines():
            clean = _normalise(line)
            if clean and not clean.lower().startswith(("extraction method", "anchor", "source anchor")) and len(clean) > 12:
                title = clean[:220]
                break

    for pat in ABSTRACT_PATTERNS:
        m = pat.search(raw)
        if m:
            abstract = _normalise(m.group("abstract"))[:3000]
            break
    if not abstract:
        lower = raw.lower()
        idx = lower.find("abstract")
        if idx >= 0:
            abstract = _normalise(raw[idx:idx + 2500])
        else:
            abstract = _normalise(raw[:2500])

    for pat in KEYWORD_PATTERNS:
        m = pat.search(raw)
        if m:
            kw_text = _normalise(m.group("keywords"))
            keywords = [k.strip(" .;,") for k in re.split(r"[,;]", kw_text) if k.strip(" .;,")]
            break

    return {"title": title, "abstract": abstract, "keywords": keywords}


def _keyphrases(text: str, limit: int = 16) -> list[str]:
    text = _normalise(text).lower()
    tokens = re.findall(r"[a-z][a-z0-9-]{2,}", text)
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    counts = Counter(tokens)
    # Preserve useful adjacent 2-grams/3-grams, then add high-signal unigrams.
    phrases: Counter[str] = Counter()
    for n in (3, 2):
        for i in range(0, max(0, len(tokens) - n + 1)):
            gram = tokens[i:i+n]
            if all(g not in STOPWORDS for g in gram):
                phrases[" ".join(gram)] += 1
    ranked: list[str] = []
    for phrase, _ in phrases.most_common(limit * 2):
        if len(ranked) >= limit:
            break
        if not any(phrase in existing or existing in phrase for existing in ranked):
            ranked.append(phrase)
    for token, _ in counts.most_common(limit * 2):
        if len(ranked) >= limit:
            break
        if token not in ranked and not any(token in existing.split() for existing in ranked[:8]):
            ranked.append(token)
    return ranked[:limit]


def _unique_terms(text: str, limit: int = 10) -> list[str]:
    tokens = re.findall(r"[a-z][a-z0-9-]{2,}", _normalise(text).lower())
    tokens = [t for t in tokens if t not in STOPWORDS and not t.isdigit()]
    counts = Counter(tokens)
    out: list[str] = []
    for token, _ in counts.most_common(limit * 3):
        if token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def _diverse_phrases(phrases: list[str], limit: int = 4) -> list[str]:
    selected: list[str] = []
    covered: set[str] = set()
    for phrase in phrases:
        words = [w for w in phrase.split() if w not in STOPWORDS]
        if not words:
            continue
        # Prefer phrases that add new terms rather than repeating the same title words.
        novelty = sum(1 for w in words if w not in covered)
        if novelty == 0:
            continue
        selected.append(phrase)
        covered.update(words)
        if len(selected) >= limit:
            break
    return selected


def generate_queries(metadata: dict[str, Any], extra_terms: list[str] | None = None, max_queries: int = 8) -> list[dict[str, Any]]:
    title = str(metadata.get("title") or "").strip()
    abstract = str(metadata.get("abstract") or "").strip()
    keywords = [str(k).strip() for k in metadata.get("keywords") or [] if str(k).strip()]
    extra_terms = [t.strip() for t in (extra_terms or []) if t.strip()]
    text_for_terms = " ".join([title, abstract, " ".join(keywords)])
    phrases = _keyphrases(text_for_terms, limit=24)
    diverse = _diverse_phrases(phrases, limit=5)
    terms = _unique_terms(text_for_terms, limit=10)

    queries: list[dict[str, Any]] = []
    seen_queries: set[str] = set()

    def add(query: str, source: str, rationale: str, confidentiality: str = "derived_short_query") -> None:
        query = re.sub(r"\s+", " ", query).strip(" .;,")
        if not query or len(query) < 8:
            return
        # Keep queries short; do not leak full abstract/manuscript.
        words = query.split()
        if len(words) > 12:
            query = " ".join(words[:12])
        key = query.lower()
        if key not in seen_queries:
            seen_queries.add(key)
            queries.append({"query": query, "source": source, "rationale": rationale, "confidentiality": confidentiality})

    if title:
        add(title, "title", "Exact-title search to find the paper itself and close neighbours.", "title_only")
    if keywords:
        add(" ".join(keywords[:6]), "keywords", "Keyword search derived from manuscript keywords.")
    if terms:
        add(" ".join(terms[:8]), "term_profile", "Compact search using the highest-signal title/abstract terms.")
    if diverse:
        add(" ".join(diverse[:3]), "phrase_profile", "Diverse phrase search derived locally from title and abstract.")
    if len(diverse) >= 5:
        add(" ".join(diverse[2:5]), "phrase_profile", "Broader phrase search for adjacent prior work.")
    for term in extra_terms[:3]:
        add(term, "user_extra_term", "User-supplied extra term combined with generated search workflow.", "user_supplied")
    return queries[:max_queries]


def build_query_plan(packet_dir: Path, out_path: Path | None = None, extra_terms: list[str] | None = None, max_queries: int = 8) -> dict[str, Any]:
    text = _read_packet_text(packet_dir)
    metadata = extract_metadata_from_text(text)
    queries = generate_queries(metadata, extra_terms=extra_terms, max_queries=max_queries)
    plan = {
        "version": "v1-pre2-retrieval",
        "source": "local_packet_text",
        "privacy_note": "Queries are short strings derived from title/abstract/keywords; full manuscript text is not sent to public metadata search APIs.",
        "metadata": metadata,
        "candidate_keyphrases": _keyphrases(" ".join([metadata.get("title", ""), metadata.get("abstract", ""), " ".join(metadata.get("keywords", []))]), limit=20),
        "queries": queries,
    }
    if out_path:
        write_json(out_path, plan)
    return plan
