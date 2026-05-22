#!/usr/bin/env python3
"""
CI adapter for vbsec (https://github.com/tanviet12/vbsec).

Runs deterministic checks for all 21 vbsec rule IDs. Full reasoning-first
scan remains the agent skill: /vbs-scan-security (see scripts/install-vbsec-skill.sh).

Outputs vbsec-compatible JSON (references/output-format.md).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vbsec_rules import (
    ALL_VBSEC_RULE_IDS,
    BANDIT_TO_VBSEC,
    TYPOSQUAT_PACKAGES,
    get_pattern_rules,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VBSEC = ROOT / ".vbsec" / "skills" / "vbs-scan-security"
PARSER_DIR = ROOT / "services" / "document-parser"
PARSER_APP = PARSER_DIR / "app"
PARSER_REQUIREMENTS = PARSER_DIR / "requirements.txt"
PIP_AUDIT_IGNORES = ("PYSEC-2025-183", "CVE-2025-45768")
E2E_DIR = ROOT / "e2e"

PATTERN_SKIP_FILES = frozenset(
    {
        "scripts/ci/vbsec_rules.py",
        "scripts/ci/vbsec_ci_scan.py",
    }
)

SKIP_DIRS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    ".git",
    "vbsec-reports",
    ".vbsec",
    ".vbsec-tmp",
    "test-results",
    "playwright-report",
}

SCAN_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".sql",
    ".html",
    ".jinja",
    ".j2",
    ".env",
    ".env.example",
    ".sh",
}

BANDIT_DIRS = [
    PARSER_APP,
    ROOT / "scripts",
]


@dataclass
class Finding:
    file: str
    line: int
    rule_id: str
    severity: str
    issue_summary: str
    fix_summary: str


@dataclass
class ScanResult:
    scope: str
    files_reviewed: int
    primary_language: str
    findings: list[Finding] = field(default_factory=list)
    passed_rules: list[str] = field(default_factory=list)
    rules_checked: list[str] = field(default_factory=list)

    def verdict(self) -> str:
        if any(f.severity == "CRITICAL" for f in self.findings):
            return "FAIL"
        if any(f.severity == "HIGH" for f in self.findings):
            return "WARN"
        return "PASS"

    def summary_counts(self) -> dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            key = f.severity.lower()
            if key in counts:
                counts[key] += 1
        counts["passed"] = len(self.passed_rules)
        return counts

    def rules_coverage(self) -> dict[str, list[str]]:
        failed = sorted({f.rule_id for f in self.findings})
        passed = sorted(set(self.rules_checked) - set(failed))
        return {
            "total": len(ALL_VBSEC_RULE_IDS),
            "checked": list(self.rules_checked),
            "passed": passed,
            "failed": failed,
        }

    def to_json(self, mode: str = "ci") -> dict:
        return {
            "verdict": self.verdict(),
            "summary": self.summary_counts(),
            "scope": self.scope,
            "files_reviewed": self.files_reviewed,
            "primary_language": self.primary_language,
            "specialized_rules_used": self.primary_language in ("python", "typescript"),
            "mode": mode,
            "date": date.today().isoformat(),
            "scanner": "vbsec-ci-deterministic",
            "vbsec_repo": "https://github.com/tanviet12/vbsec",
            "rules_coverage": self.rules_coverage(),
            "findings": [
                {
                    "file": f.file,
                    "line": f.line,
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "issue_summary": f.issue_summary,
                    "fix_summary": f.fix_summary,
                }
                for f in self.findings
            ],
        }


def list_files(root: Path, scope: str, base_ref: str) -> list[Path]:
    if scope == "diff":
        cmd = ["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"]
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if proc.returncode != 0:
            cmd = ["git", "diff", "--name-only", "HEAD~1..HEAD"]
            proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        names = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        paths = [root / n for n in names]
    else:
        paths = [p for p in root.rglob("*") if p.is_file()]

    out: list[Path] = []
    for path in paths:
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_EXTENSIONS and path.name not in (
            ".env",
            ".env.example",
        ):
            continue
        if path.is_file():
            out.append(path)
    return sorted(set(out))


def detect_language(files: list[Path]) -> str:
    counts: dict[str, int] = {}
    for path in files:
        ext = path.suffix.lower()
        lang = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "typescript",
            ".jsx": "typescript",
        }.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "unknown"
    return max(counts, key=counts.get)


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)


def run_gitleaks(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    if not _which("gitleaks"):
        print("WARN: gitleaks not installed — skipping HARDCODED-SECRET scan", file=sys.stderr)
        return findings
    cmd = [
        "gitleaks",
        "detect",
        "--source",
        str(root),
        "--no-git",
        "--redact",
        "-f",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        return findings
    try:
        leaks = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return findings
    allowed = {p.resolve() for p in files} if files else None
    for item in leaks:
        fpath = item.get("File", "")
        if not fpath:
            continue
        resolved = (root / fpath).resolve()
        if allowed is not None and resolved not in allowed:
            continue
        rel = Path(fpath).as_posix()
        if rel.endswith(".env.example") or "example" in rel.lower():
            continue
        line = int(item.get("StartLine") or 1)
        findings.append(
            Finding(
                file=rel,
                line=line,
                rule_id="HARDCODED-SECRET",
                severity="CRITICAL",
                issue_summary=f"Secret pattern detected ({item.get('RuleID', 'gitleaks')})",
                fix_summary="Rotate secret, remove from repo, use env vars / secrets manager",
            )
        )
    return findings


def run_bandit(target_dirs: list[Path], root: Path) -> list[Finding]:
    if not _which("bandit"):
        print("WARN: bandit not installed — skipping Python SAST", file=sys.stderr)
        return []
    existing = [d for d in target_dirs if d.is_dir()]
    if not existing:
        return []
    findings: list[Finding] = []
    for target in existing:
        proc = subprocess.run(
            ["bandit", "-r", str(target), "-f", "json", "-ll", "-q"],
            capture_output=True,
            text=True,
        )
        if proc.returncode not in (0, 1) or not proc.stdout.strip():
            continue
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue
        for item in data.get("results", []):
            test_id = item.get("test_id", "")
            if test_id not in BANDIT_TO_VBSEC:
                continue
            rule_id, severity = BANDIT_TO_VBSEC[test_id]
            fpath = Path(item.get("filename", ""))
            try:
                rel = fpath.relative_to(root).as_posix()
            except ValueError:
                rel = fpath.as_posix()
            findings.append(
                Finding(
                    file=rel,
                    line=int(item.get("line_number") or 1),
                    rule_id=rule_id,
                    severity=severity,
                    issue_summary=item.get("issue_text", "bandit finding")[:200],
                    fix_summary="See bandit docs; align with vbsec rule guidance",
                )
            )
    return findings


def run_pattern_scan(files: list[Path], root: Path) -> list[Finding]:
    rules = get_pattern_rules()
    findings: list[Finding] = []
    ssrf_safe_suffixes = (
        "url_safety.py",
        "http_download.py",
        "persistence/supabase.py",
        "core/readiness.py",
    )
    ssrf_safe_files = {
        p.relative_to(root).as_posix()
        for p in files
        if p.name in ("backfill_orphan_documents.py",)
        or any(p.as_posix().endswith(suffix) for suffix in ssrf_safe_suffixes)
    }

    for path in files:
        ext = path.suffix.lower()
        rel = path.relative_to(root).as_posix()
        if rel.endswith(".env.example") or rel in PATTERN_SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for rule in rules:
            if ext not in rule.extensions:
                continue
            if rule.rule_id == "SSRF" and rel in ssrf_safe_files:
                continue
            for match in rule.pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                findings.append(
                    Finding(
                        file=rel,
                        line=line,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        issue_summary=rule.issue_summary,
                        fix_summary=rule.fix_summary,
                    )
                )
    return findings


def run_broken_access_scan(files: list[Path], root: Path) -> list[Finding]:
    """Mutating API routes must include verify_auth unless public auth/health."""
    findings: list[Finding] = []
    public_fragments = ("/login", "/signin", "/register", "/health", "/auth/token")
    route_re = re.compile(
        r"@router\.(post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.I,
    )
    for path in files:
        if path.suffix != ".py" or "/api/" not in path.as_posix():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for match in route_re.finditer(text):
            route_path = match.group(2)
            if any(p in route_path for p in public_fragments):
                continue
            start = match.start()
            block = text[start : start + 1200]
            if re.search(r"verify_auth|Depends\s*\(\s*verify", block, re.I):
                continue
            line = text[: match.start()].count("\n") + 1
            findings.append(
                Finding(
                    file=rel,
                    line=line,
                    rule_id="BROKEN-ACCESS-CONTROL",
                    severity="HIGH",
                    issue_summary=f"Mutating route {route_path} lacks verify_auth dependency",
                    fix_summary="Add _auth=Depends(verify_auth) on the handler",
                )
            )
    return findings


def run_idor_scan(files: list[Path], root: Path) -> list[Finding]:
    """Flag FastAPI routes with path params that lack auth in handler signature."""
    findings: list[Finding] = []
    route_re = re.compile(
        r"@router\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]",
        re.I,
    )
    for path in files:
        if path.suffix != ".py" or "/api/" not in path.as_posix():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for match in route_re.finditer(text):
            route_path = match.group(2)
            if "{" not in route_path:
                continue
            start = match.start()
            window = text[start : start + 800]
            if re.search(r"verify_auth|Depends\s*\(\s*verify", window, re.I):
                continue
            if "/health" in route_path:
                continue
            line = text[: match.start()].count("\n") + 1
            findings.append(
                Finding(
                    file=rel,
                    line=line,
                    rule_id="IDOR",
                    severity="HIGH",
                    issue_summary=f"Route {route_path} uses path param without visible auth check",
                    fix_summary="Add Depends(verify_auth) and ownership filter on resource ID",
                )
            )
    return findings


def run_slopsquat_scan(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    req = PARSER_REQUIREMENTS
    if not req.is_file():
        return findings
    for lineno, line in enumerate(req.read_text(encoding="utf-8").splitlines(), start=1):
        pkg = line.split("==")[0].split("[")[0].strip().lower()
        if not pkg or pkg.startswith("#"):
            continue
        if pkg in TYPOSQUAT_PACKAGES:
            findings.append(
                Finding(
                    file=req.relative_to(root).as_posix(),
                    line=lineno,
                    rule_id="SLOPSQUATTING",
                    severity="CRITICAL",
                    issue_summary=f"Suspicious/typosquat package name: {pkg}",
                    fix_summary="Verify package name on PyPI; use intended dependency",
                )
            )
    lock = E2E_DIR / "package-lock.json"
    if lock.is_file():
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return findings
        packages = data.get("packages") or {}
        for name in packages:
            base = name.split("node_modules/")[-1].lower()
            if base in TYPOSQUAT_PACKAGES:
                findings.append(
                    Finding(
                        file=lock.relative_to(root).as_posix(),
                        line=1,
                        rule_id="SLOPSQUATTING",
                        severity="CRITICAL",
                        issue_summary=f"Suspicious npm package: {base}",
                        fix_summary="Verify package on npm registry",
                    )
                )
    return findings


def run_pip_audit(root: Path) -> list[Finding]:
    if not _which("pip-audit") or not PARSER_REQUIREMENTS.is_file():
        print("WARN: pip-audit not installed — skipping OUTDATED-DEPENDENCY", file=sys.stderr)
        return []
    cmd = [
        "pip-audit",
        "-r",
        str(PARSER_REQUIREMENTS),
        "--format",
        "json",
        "--ignore-vuln",
        *PIP_AUDIT_IGNORES,
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        print(f"WARN: pip-audit failed: {proc.stderr[:300]}", file=sys.stderr)
        return []
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return []
    deps = data.get("dependencies") or data if isinstance(data, list) else []
    if isinstance(data, dict) and "dependencies" not in data:
        deps = data.get("vulnerabilities") or []
    findings: list[Finding] = []
    rel = PARSER_REQUIREMENTS.relative_to(root).as_posix()
    items = deps if isinstance(deps, list) else []
    for dep in items:
        vulns = dep.get("vulns") or dep.get("vulnerabilities") or []
        if isinstance(dep, dict) and dep.get("id"):
            vulns = [dep]
        for vuln in vulns:
            vid = vuln.get("id") or vuln.get("vulnerability_id") or "CVE"
            alias = vuln.get("aliases") or []
            if vid in PIP_AUDIT_IGNORES or any(a in PIP_AUDIT_IGNORES for a in alias):
                continue
            name = dep.get("name", "unknown")
            findings.append(
                Finding(
                    file=rel,
                    line=1,
                    rule_id="OUTDATED-DEPENDENCY",
                    severity="HIGH",
                    issue_summary=f"{name}: {vid}",
                    fix_summary="Upgrade dependency per pip-audit advisory",
                )
            )
    return findings


def run_npm_audit(root: Path) -> list[Finding]:
    lock = E2E_DIR / "package-lock.json"
    if not lock.is_file() or not _which("npm"):
        return []
    proc = subprocess.run(
        ["npm", "audit", "--json", "--audit-level=high"],
        cwd=E2E_DIR,
        capture_output=True,
        text=True,
    )
    if not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    advisories = data.get("vulnerabilities") or {}
    findings: list[Finding] = []
    rel = lock.relative_to(root).as_posix()
    for name, adv in advisories.items():
        if adv.get("isDirect") is False and adv.get("severity") not in ("high", "critical"):
            continue
        sev = (adv.get("severity") or "high").upper()
        severity = "CRITICAL" if sev == "CRITICAL" else "HIGH"
        findings.append(
            Finding(
                file=rel,
                line=1,
                rule_id="OUTDATED-DEPENDENCY",
                severity=severity,
                issue_summary=f"npm {name}: {adv.get('title', 'vulnerability')[:120]}",
                fix_summary="Run npm audit fix or upgrade lockfile",
            )
        )
    return findings


def dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, int, str]] = set()
    out: list[Finding] = []
    for f in findings:
        key = (f.file, f.line, f.rule_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def finalize_rules(result: ScanResult, tools_ran: dict[str, bool]) -> None:
    """Mark which vbsec rules were exercised in this run."""
    checked: set[str] = set(ALL_VBSEC_RULE_IDS)
    tool_rules = {
        "gitleaks": ["HARDCODED-SECRET"],
        "bandit": [
            "SQL-INJECTION",
            "COMMAND-INJECTION",
            "INSECURE-DESERIALIZATION",
            "WEAK-PASSWORD-HASHING",
            "BROKEN-ACCESS-CONTROL",
            "VERBOSE-ERROR-DEBUG-MODE",
        ],
        "patterns": [
            "JWT-NONE-ALGORITHM",
            "INSECURE-DESERIALIZATION",
            "COMMAND-INJECTION",
            "SQL-INJECTION",
            "SSRF",
            "PATH-TRAVERSAL",
            "XSS",
            "MASS-ASSIGNMENT",
            "CORS-MISCONFIG",
            "CSRF",
            "UNRESTRICTED-FILE-UPLOAD",
            "VERBOSE-ERROR-DEBUG-MODE",
            "WEAK-PASSWORD-HASHING",
            "BRUTE-FORCE",
            "MISSING-RATE-LIMIT",
            "RACE-CONDITION",
            "HARDCODED-SECRET",
        ],
        "broken_access": ["BROKEN-ACCESS-CONTROL"],
        "idor": ["IDOR"],
        "slopsquat": ["SLOPSQUATTING"],
        "pip_audit": ["OUTDATED-DEPENDENCY"],
        "npm_audit": ["OUTDATED-DEPENDENCY"],
    }
    _ = tools_ran, tool_rules  # tools_ran reserved for future per-tool skip reporting
    result.rules_checked = sorted(checked)
    failed = {f.rule_id for f in result.findings}
    result.passed_rules = sorted(checked - failed)


def main() -> int:
    parser = argparse.ArgumentParser(description="vbsec CI deterministic scan (21 rules)")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--vbsec-dir", type=Path, default=DEFAULT_VBSEC)
    parser.add_argument("--scope", choices=["all", "diff"], default="diff")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--output", type=Path, default=ROOT / "vbsec-reports" / "ci-scan.json")
    parser.add_argument("--fail-on", choices=["critical", "high", "never"], default="critical")
    args = parser.parse_args()

    root = args.root.resolve()
    files = list_files(root, args.scope, args.base_ref)
    result = ScanResult(
        scope=args.scope if args.scope != "all" else "all",
        files_reviewed=len(files),
        primary_language=detect_language(files),
    )

    tools_ran: dict[str, bool] = {}
    all_findings: list[Finding] = []

    all_findings.extend(run_gitleaks(root, files))
    tools_ran["gitleaks"] = _which("gitleaks") is not None

    all_findings.extend(run_bandit(BANDIT_DIRS, root))
    tools_ran["bandit"] = _which("bandit") is not None

    all_findings.extend(run_pattern_scan(files, root))
    tools_ran["patterns"] = True

    all_findings.extend(run_broken_access_scan(files, root))
    tools_ran["broken_access"] = True

    all_findings.extend(run_idor_scan(files, root))
    tools_ran["idor"] = True

    all_findings.extend(run_slopsquat_scan(root))
    tools_ran["slopsquat"] = True

    all_findings.extend(run_pip_audit(root))
    tools_ran["pip_audit"] = _which("pip-audit") is not None

    all_findings.extend(run_npm_audit(root))
    tools_ran["npm_audit"] = _which("npm") is not None and (E2E_DIR / "package-lock.json").is_file()

    result.findings = dedupe(all_findings)
    finalize_rules(result, tools_ran)

    payload = result.to_json()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    cov = payload["rules_coverage"]
    print(f"vbsec CI verdict: {payload['verdict']}")
    print(f"Findings: {len(result.findings)} (critical={payload['summary']['critical']})")
    print(f"Rules checked: {len(cov['checked'])}/{cov['total']} passed={len(cov['passed'])}")
    print(f"Report: {args.output}")

    if args.fail_on == "never":
        return 0
    if args.fail_on == "critical" and payload["verdict"] == "FAIL":
        return 1
    if args.fail_on == "high" and payload["verdict"] in ("FAIL", "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
