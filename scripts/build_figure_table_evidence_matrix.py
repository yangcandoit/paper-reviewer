from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewer_core.figure_table import write_figure_table_matrix

def main() -> None:
    ap = argparse.ArgumentParser(description="Build a figure/table evidence matrix from PDF visual and caption candidates.")
    ap.add_argument("packet", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = write_figure_table_matrix(args.packet, args.out)
    print(f"entry_count={report['entry_count']} status={report['status']}")
if __name__ == "__main__": main()
