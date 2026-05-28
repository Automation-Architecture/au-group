#!/usr/bin/env python3
"""Fail CI if any au-group-sys-* workflow JSON contains Code nodes (NFR-7.1 no-Code bar)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PULLED = ROOT / "workflows" / "pulled"

def main() -> int:
    failures: list[str] = []
    for path in sorted(PULLED.glob("au-group-sys-*.json")):
        data = json.loads(path.read_text())
        codes = [n["name"] for n in data.get("nodes", []) if n.get("type") == "n8n-nodes-base.code"]
        if codes:
            failures.append(f"{path.name}: {', '.join(codes)}")
    if failures:
        print("Code nodes found (expected 0 for full no-Code compliance):")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("OK: 0 Code nodes in workflows/pulled/au-group-sys-*.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())
