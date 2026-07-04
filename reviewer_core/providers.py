from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import base64
import json
import mimetypes
import os
import time
import urllib.request
import urllib.error


class LLMProvider(Protocol):
    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: str,
        step_id: str,
        visual_assets: list[Path] | None = None,
    ) -> str: ...


@dataclass
class MockProvider:
    """Offline provider for tests, demos, and workflow dry-runs."""
    reviewer_name: str = "mock"

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: str,
        step_id: str,
        visual_assets: list[Path] | None = None,
    ) -> str:
        issue_id = f"{step_id.upper().replace('-', '_')}-INFO-001"
        visual_note = f"\n\nVisual assets made available to this step: {len(visual_assets or [])}." if visual_assets else ""
        return f"""# {step_id.replace('_', ' ').title()}

## Review summary
This is an offline mock output generated to test the workflow runner. Replace the
provider with an OpenAI-compatible endpoint or run the prompt manually for a real review.{visual_note}

## Issues
No manuscript-specific issue has been asserted by the mock provider.

```json
{{
  "issues": [
    {{
      "issue_id": "{issue_id}",
      "title": "Mock output requires real model review",
      "source_reviewer": "{self.reviewer_name}",
      "severity": "P3",
      "evidence_location": "information_gap: offline mock provider",
      "evidence_type": "information_gap",
      "confidence": "High",
      "fix_type": "verification needed",
      "required_action": "Run this step with a real LLM provider or manually apply the prompt to the review packet.",
      "new_experiment_needed": false,
      "expected_impact": "Enables real manuscript-specific feedback.",
      "status": "open"
    }}
  ]
}}
```
"""


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _image_data_url(path: Path, max_bytes: int) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except Exception:
        return None


def _safe_visual_asset_label(path: Path) -> str | None:
    """Return a non-absolute, non-user-specific label for a visual asset.

    Provider calls intentionally do not know the review packet root. Visual
    assets collected by the workflow live below ``derived/`` inside a packet,
    so the safest useful label is the path suffix starting at that component.
    If that cannot be computed, callers should fall back to a generic note
    rather than exposing an absolute local path.
    """
    try:
        parts = Path(path).resolve(strict=False).parts
    except Exception:
        return None
    if "derived" not in parts:
        return None
    idx = parts.index("derived")
    rel = Path(*parts[idx:])
    if rel.is_absolute() or ".." in rel.parts:
        return None
    label = rel.as_posix()
    return label or None


def _visual_assets_not_sent_note(image_paths: list[Path]) -> str:
    labels = [_safe_visual_asset_label(path) for path in image_paths]
    labels = [label for label in labels if label]
    note = (
        "\n\n[Vision note: visual assets are available locally but were not sent. "
        "Set AI_REVIEWER_SEND_IMAGES=1 with a vision-capable model, or review the local visual bundle manually.]"
    )
    if labels:
        note += "\nLocal packet-relative visual asset references:\n" + "\n".join(f"- {label}" for label in labels)
    return note


@dataclass
class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible Chat Completions client.

    Works with text-only models and, optionally, vision-capable OpenAI-compatible
    chat models. Visual assets are sent only when send_images=True, which can be
    enabled with AI_REVIEWER_SEND_IMAGES=1. Keeping image sending opt-in prevents
    accidental upload of manuscript figures/pages.
    """
    model: str
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.2
    timeout: int = 120
    max_tokens: int | None = None
    retries: int = 2
    send_images: bool = False
    max_images: int = 8
    max_image_bytes: int = 2_500_000

    @classmethod
    def from_env(cls) -> "OpenAICompatibleProvider":
        return cls(
            model=os.environ.get("AI_REVIEWER_MODEL", "gpt-4.1-mini"),
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_REVIEWER_API_KEY"),
            base_url=os.environ.get("AI_REVIEWER_BASE_URL", "https://api.openai.com/v1"),
            temperature=float(os.environ.get("AI_REVIEWER_TEMPERATURE", "0.2")),
            timeout=int(os.environ.get("AI_REVIEWER_TIMEOUT", "120")),
            max_tokens=int(os.environ["AI_REVIEWER_MAX_TOKENS"]) if os.environ.get("AI_REVIEWER_MAX_TOKENS") else None,
            send_images=_truthy(os.environ.get("AI_REVIEWER_SEND_IMAGES")),
            max_images=int(os.environ.get("AI_REVIEWER_MAX_IMAGES", "8")),
            max_image_bytes=int(os.environ.get("AI_REVIEWER_MAX_IMAGE_BYTES", "2500000")),
        )

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: str,
        step_id: str,
        visual_assets: list[Path] | None = None,
    ) -> str:
        if not self.api_key and "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
            raise RuntimeError("Missing API key. Set OPENAI_API_KEY or AI_REVIEWER_API_KEY, or use --provider mock.")
        url = self.base_url.rstrip("/") + "/chat/completions"
        text_content = prompt + "\n\n# Review packet context\n" + context
        image_paths = list(visual_assets or [])[: self.max_images]
        skipped_images = 0
        if image_paths and self.send_images:
            content_parts: list[dict] = [{"type": "text", "text": text_content}]
            for path in image_paths:
                data_url = _image_data_url(path, self.max_image_bytes)
                if data_url is None:
                    skipped_images += 1
                    continue
                content_parts.append({"type": "image_url", "image_url": {"url": data_url}})
            if skipped_images:
                content_parts[0]["text"] += f"\n\n[Vision note: {skipped_images} image(s) exceeded AI_REVIEWER_MAX_IMAGE_BYTES and were not sent.]"
            user_content: str | list[dict] = content_parts
        else:
            if image_paths:
                text_content += _visual_assets_not_sent_note(image_paths[: self.max_images])
            user_content = text_content
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
        raise RuntimeError(f"LLM provider failed for step {step_id}: {last_error}")


def get_provider(name: str) -> LLMProvider:
    normalized = name.strip().lower()
    if normalized in {"mock", "dry-run", "offline"}:
        return MockProvider()
    if normalized in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleProvider.from_env()
    raise ValueError(f"Unknown provider: {name}. Use mock or openai-compatible.")
