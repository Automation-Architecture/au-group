#!/usr/bin/env python3
"""Validate export/aaa-client-dashboard/au-group data package (CI gate)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = ROOT / "export" / "aaa-client-dashboard" / "au-group"
DATA_DIR = EXPORT_DIR / "data"
PROJECT_CONFIG = ROOT / "project.config.yaml"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_FILES = {
    "sprint-progress.json": {"slug", "jiraProjectKey", "sprintName"},
    "github_activity.json": {"slug", "githubRepo"},
    "documents.json": {"slug", "documents"},
    "horizon.json": {"slug", "milestones"},
    "weekly_updates.json": {"slug", "updates"},
}


def load_project_config() -> dict:
    if yaml is None:
        print("PyYAML required", file=sys.stderr)
        sys.exit(1)
    with PROJECT_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["project"]


def check_dates(obj: object, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("date", "start", "end", "launchTarget") and isinstance(v, str):
                if v and not ISO_DATE.match(v):
                    errors.append(f"{path}.{k}: invalid ISO date {v!r}")
            check_dates(v, f"{path}.{k}", errors)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            check_dates(item, f"{path}[{i}]", errors)


def main() -> int:
    errors: list[str] = []
    project = load_project_config()
    slug = project.get("slug")
    jira_key = project.get("jira_project_key")

    patch_yml = EXPORT_DIR / "patches" / "sync-jira-workflow-step.yml"
    if not patch_yml.is_file():
        errors.append(f"missing {patch_yml}")
    else:
        if yaml:
            with patch_yml.open(encoding="utf-8") as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as exc:
                    errors.append(f"invalid YAML in sync-jira patch: {exc}")

    for filename, required_keys in REQUIRED_FILES.items():
        path = DATA_DIR / filename
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: {exc}")
            continue
        missing = required_keys - set(data.keys())
        if missing:
            errors.append(f"{path}: missing keys {missing}")
        if data.get("slug") != slug:
            errors.append(f"{path}: slug must be {slug!r}, got {data.get('slug')!r}")
        if filename == "sprint-progress.json" and data.get("jiraProjectKey") != jira_key:
            errors.append(
                f"{path}: jiraProjectKey must be {jira_key!r}, got {data.get('jiraProjectKey')!r}"
            )
        check_dates(data, filename, errors)

    if errors:
        print("Export package validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK: export package for slug={slug!r} jira={jira_key!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
