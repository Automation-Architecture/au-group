# Security CI layers (document-parser)

Layered checks on every PR/push via [`ci.yml`](../../.github/workflows/ci.yml), plus deploy workflows for the parser.

| Layer | Tool | Workflow | What it catches |
|-------|------|----------|-----------------|
| SAST (patterns) | vbsec + Bandit + regex | [`ci-security.yml`](../../.github/workflows/ci-security.yml) | OWASP-style issues, FastAPI heuristics, 21 rule IDs |
| SAST (dataflow) | CodeQL | [`ci-codeql.yml`](../../.github/workflows/ci-codeql.yml) | SQLi, SSRF, path traversal, insecure deserialization |
| Secrets | Gitleaks | `ci-security` | API keys, tokens in repo |
| Dependencies | pip-audit (+ npm audit for e2e) | `ci-security`, [`ci-parser.yml`](../../.github/workflows/ci-parser.yml) | CVEs in Python/Node lockfiles |
| Container | Trivy | [`ci-container-scan.yml`](../../.github/workflows/ci-container-scan.yml) | OS + library vulns in Docker image (EC2 path) |

## GitHub Security tab

- **vbsec:** gitleaks + bandit SARIF (`run-vbsec` composite)
- **CodeQL:** native analysis upload
- **Trivy:** container SARIF (`continue-on-error` on upload if Advanced Security is off)

Enable **Settings → Code security →** Dependabot alerts and code scanning for full UI integration.

## Scope

- CodeQL paths: [`codeql-config.yml`](../../.github/codeql/codeql-config.yml) — `app/` + `scripts/`, not tests
- Trivy builds [`services/document-parser/Dockerfile`](../../services/document-parser/Dockerfile) (same image as optional EC2 deploy)
- `trivy-action` is pinned to a **full commit SHA** (`v0.36.0`), not `@0.28.0` — upstream tags use a `v` prefix and older numeric tags were removed ([GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23))

## Not in CI (by design)

| Tool | Reason |
|------|--------|
| Semgrep | Overlaps Bandit + vbsec; add only if custom rule packs are needed |
| OWASP ZAP | Needs stable staging API + secrets; use post-deploy smoke / manual until staging URL is a repo variable |

## Related

- [vbsec](./vbsec.md) — rule mapping and local commands
- [requirements-traceability](./requirements-traceability.md) — NFR-5 / AU_GROUP-8.5
