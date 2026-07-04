#!/usr/bin/env python3
"""Run a tiny provider smoke test without sending a manuscript."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reviewer_core.providers import get_provider


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="mock", choices=["mock", "openai-compatible", "openai"])
    args = ap.parse_args()
    provider = get_provider(args.provider)
    text = provider.generate(
        system="You are a connection test assistant.",
        prompt="Return one short sentence and one JSON issue list with no manuscript-specific claims.",
        context="No manuscript context is included in this connection test.",
        step_id="provider_connection_test",
    )
    print(text[:2000])


if __name__ == "__main__":
    main()
