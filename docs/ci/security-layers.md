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
- **No Docker build** in CI — but note [`Dockerfile`](../../services/document-parser/Dockerfile) is **not** EC2-only: Railway builds every service from it (verified 2026-08-13; `nixpacks.toml` is unused). So Dockerfile changes ship to production without a CI image build to catch them.

## Not in CI (by design)

| Tool | Reason |
|------|--------|
| `trivy-action` + image scan | Slow, duplicates pip-audit; OS CVEs in base image are not actionable in this repo’s deploy path |
| Semgrep | Overlaps Bandit + vbsec |
| OWASP ZAP | Needs stable staging API + secrets |

## Supabase RPC ACL (post-migrate)

After `supabase db reset --local` or production `db push`:

```bash
./scripts/ci/verify-supabase-rpc-acl.sh
psql "$DB_URL" -f scripts/supabase/verify-rpc-acl.sql
```

`au_group_*` functions must be **service_role** only (no `anon` / `authenticated` execute). Migrations: `20260602150600_*` + **`20260602150900_security_rpc_acl_reapply.sql`** (must stay last when adding new `au_group_*` RPCs).

KD-40 merge smoke: `scripts/supabase/smoke_merge_creditor_matrix_dedup_audit.sql` (runs in `ci-supabase.yml`). Requires `20260602150700` (drops legacy `(uuid, jsonb)` overload).

## Related

- [vbsec](./vbsec.md) — rule mapping and local commands
- [requirements-traceability](./requirements-traceability.md) — NFR-5 / AU_GROUP-8.5
