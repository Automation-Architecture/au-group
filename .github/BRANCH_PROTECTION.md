# Branch protection checklist (manual GitHub setup)

Apply to branch **`main`** in repository settings.

## Required status checks

Enable **Require status checks to pass** and select:

- `CI / all-green` (from [`.github/workflows/ci.yml`](workflows/ci.yml))

Recommended additional checks (appear when paths match):

- `lint-test-audit` / `CI — document-parser`
- `integration` / `Integration tests (document-parser)` (parser paths)
- `migrate-reset` / `CI — Supabase migrations`
- `vbsec` / `CI — vbsec security` (**every PR**)
- `analyze` / `CI — CodeQL` (**every PR**)
- `trivy-fs` / `CI — Trivy (parser deps)` (**every PR**)
- `validate` / `CI — AAA dashboard export` (from [`.github/workflows/ci-export.yml`](workflows/ci-export.yml), path-filtered in `ci.yml`)

## Pull request rules

- [ ] Require a pull request before merging
- [ ] Require approvals: **1**
- [ ] Dismiss stale pull request approvals when new commits are pushed
- [ ] **Do not** enable auto-merge (merge queue / bot merge) — auto-fix may push commits; humans merge after CI

## Auto-fix (no auto-merge)

- **Automatic** on new CodeRabbit / Copilot **review** comments → [`.github/workflows/pr-autofix.yml`](.github/workflows/pr-autofix.yml)
- **Hardened:** fork PR = comments only; commits limited to `services/document-parser/`
- Manual: `/autofix` (OWNER|MEMBER) or label `autofix` (write+)
- Cursor agent: **off** unless `AUTOFIX_CURSOR_ENABLED=true`
- Details: [`docs/ci/pr-autofix.md`](../docs/ci/pr-autofix.md)

## Environments

Create **staging** and **production** under Settings → Environments:

- **staging**: Optional for PR integration tests (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`); set repo variable `INTEGRATION_CI_STRICT=true` once secrets exist
- **production**: Required reviewers (1+), deployment branches = `main` only; `PARSER_PRODUCTION_URL`, `N8N_*` for strict smoke

## Secrets

Copy the table from [`docs/ci/environments.md`](../docs/ci/environments.md) into each environment.

## Dependabot

[`.github/dependabot.yml`](dependabot.yml) is enabled; ensure Dependabot security updates are on in repo settings.
