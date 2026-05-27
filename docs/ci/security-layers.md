# Security CI layers (document-parser)

Layered checks on every PR/push via [`ci.yml`](../../.github/workflows/ci.yml), plus deploy workflows for the parser.

| Layer | Tool | Workflow | What it catches |
|-------|------|----------|-----------------|
| SAST (patterns) | vbsec + Bandit + regex | [`ci-security.yml`](../../.github/workflows/ci-security.yml) | OWASP-style issues, FastAPI heuristics, 21 rule IDs |
| SAST (dataflow) | CodeQL | [`ci-codeql.yml`](../../.github/workflows/ci-codeql.yml) | SQLi, SSRF, path traversal, insecure deserialization |
| Secrets | Gitleaks | `ci-security` | API keys, tokens in repo |
| Dependencies | pip-audit (+ npm audit for e2e) | `ci-security`, [`ci-parser.yml`](../../.github/workflows/ci-parser.yml) | CVEs in Python/Node lockfiles |
| Dependencies (2nd opinion) | Trivy fs | [`ci-trivy.yml`](../../.github/workflows/ci-trivy.yml) | CVEs in `services/document-parser/` (no Docker build) |

## GitHub Security tab

- **vbsec:** gitleaks + bandit SARIF (`run-vbsec` composite)
- **CodeQL:** native analysis upload
- **Trivy:** filesystem SARIF (`continue-on-error` on upload if Advanced Security is off)

Enable **Settings → Code security →** Dependabot alerts and code scanning for full UI integration.

## Scope

- CodeQL paths: [`codeql-config.yml`](../../.github/codeql/codeql-config.yml) — `app/` + `scripts/`, not tests
- Trivy: [`install-trivy.sh`](../../scripts/ci/install-trivy.sh) pins CLI **v0.69.3**; scans `services/document-parser/` only
- Ignores align with [`pip-audit.toml`](../../services/document-parser/pip-audit.toml) via [`.trivyignore`](../../services/document-parser/.trivyignore)
- **No Docker** in CI — Railway uses nixpacks; optional [`Dockerfile`](../../services/document-parser/Dockerfile) is for EC2 only

## Not in CI (by design)

| Tool | Reason |
|------|--------|
| `trivy-action` + image scan | Slow, duplicates pip-audit; OS CVEs in base image are not actionable in this repo’s deploy path |
| Semgrep | Overlaps Bandit + vbsec |
| OWASP ZAP | Needs stable staging API + secrets |

## Related

- [vbsec](./vbsec.md) — rule mapping and local commands
- [requirements-traceability](./requirements-traceability.md) — NFR-5 / AU_GROUP-8.5
