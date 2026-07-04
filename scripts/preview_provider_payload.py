#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.privacy import write_provider_payload_preview

def main() -> None:
    ap = argparse.ArgumentParser(description="Preview what a remote provider workflow may receive. Does not send data.")
    ap.add_argument("packet", type=Path)
    ap.add_argument("--out", type=Path, default=Path("."))
    args = ap.parse_args()
    report = write_provider_payload_preview(args.packet, args.out)
    print(f"text_files={report['text_file_count']} images={report['image_count']} images_sent={report['page_images_will_be_sent']}")
if __name__ == "__main__":
    main()
