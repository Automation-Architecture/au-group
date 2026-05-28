#!/usr/bin/env python3
"""Fail if workflow connections reference missing node names."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def validate(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    names = {n["name"] for n in data.get("nodes", [])}
    errors: list[str] = []
    for src, spec in data.get("connections", {}).items():
        if src not in names:
            errors.append(f"{path.name}: connection source missing node {src!r}")
        for branch in spec.get("main", []):
            for target in branch:
                tgt = target.get("node")
                if tgt and tgt not in names:
                    errors.append(f"{path.name}: {src!r} -> missing node {tgt!r}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[2] / "workflows/pulled"
    paths = sorted(root.glob("au-group-sys-*.json"))
    all_errors: list[str] = []
    for p in paths:
        all_errors.extend(validate(p))
    if all_errors:
        for e in all_errors:
            print(e, file=sys.stderr)
        return 1
    print(f"OK: {len(paths)} workflows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
