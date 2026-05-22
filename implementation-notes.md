# Implementation notes — GitHub Actions platform features

**Date:** 2026-05-21  
**Scope:** Integrate CI platform improvements from architecture review, **excluding n8n CI and AWS OIDC**.

## Delivered

| Feature | Location |
|---------|----------|
| Composite: parser setup | `.github/actions/setup-parser-ci/` |
| Composite: vbsec + SARIF | `.github/actions/run-vbsec/` |
| Scanner install script | `scripts/ci/install-security-scanners.sh` |
| SARIF generation | `scripts/ci/generate-security-sarif.sh` |
| Export validation CI | `.github/workflows/ci-export.yml` + path filter in `ci.yml` |
| Deploy concurrency locks | `deploy-supabase.yml`, `deploy-parser-railway.yml`, `deploy-parser-ec2.yml` |
| SARIF permissions | `security-events: write` on `ci.yml`, `ci-security.yml`, deploy workflows |

## Refactored workflows

- `ci-parser.yml`, `ci-playwright.yml`, `integration-tests.yml` → `setup-parser-ci`
- `ci-security.yml` → `run-vbsec` (shorter; logic centralized)

## Explicitly out of scope (per request)

- n8n workflow pytest job (`tests/n8n/`)
- AWS OIDC / IAM federation for integration secrets

## Copilot / missing `ci-export.yml` (2026-05-21)

- **Root cause:** `.gitignore` had bare `workflows`, which also ignored `.github/workflows/ci-export.yml`. File existed locally but was never committed; reusable workflow call failed on GitHub.
- **Fix:** Ignore only repo-root n8n exports: `/workflows/` and `/workflows/pulled`. Staged `ci-export.yml` for commit.

## PR trigger (2026-05-21)

- `ci.yml` `pull_request` has no `branches:` filter — runs on every PR once workflow files exist on the **base** branch.
- See `docs/ci/pull-request-ci.md` for the “first PR / only Copilot” limitation.

## Manual follow-up (GitHub UI)

- **Environments:** Ensure `staging` / `production` have required reviewers on production (see `.github/BRANCH_PROTECTION.md`).
- **Branch protection:** Optional required check `validate` / `CI — AAA dashboard export` after first green run on `main`.
- **Code scanning:** SARIF upload uses `github/codeql-action/upload-sarif`; enable **Code security** / Dependabot alerts if the Security tab stays empty.

## Supabase CI port 54322 (2026-05-21)

- **Symptom A:** `supabase db start` fails on GHA with `failed to bind host port ... 54322: address already in use` after a new `ghcr.io/supabase/postgres` image pull.
- **Cause A:** Intermittent Docker port-release race on hosted runners ([supabase/setup-cli#265](https://github.com/supabase/setup-cli/issues/265)).
- **Symptom B:** `supabase db reset` fails with `supabase start is not running` on every retry.
- **Cause B:** Regression from calling `supabase stop` before `db reset`; reset requires Postgres already up (`db start` first).
- **Fix:** `ci-supabase.yml` — per attempt: `supabase db start` then `db reset --local --yes`; only `stop`/`docker rm` between failed attempts; `if: always()` stop at end.

## Supabase CI RLS verify (2026-05-22)

- **Symptom:** `verify-supabase-rls.sh` failed with `Could not resolve local DB_URL` even when migrate-reset succeeded.
- **Cause:** `Stop Supabase local` (`if: always()`) ran immediately after migrations, before `db lint` and RLS verify — `supabase status` had no running DB.
- **Fix:** Move stop step to the last job step; `verify-supabase-rls.sh` also falls back to `supabase status -o env` when JSON lacks `DB_URL`.

## PR review follow-ups (2026-05-21)

- **vbsec SSRF:** Patterns in `vbsec_rules.py` now match request-derived URL args only; allowlist extended for Supabase/readiness clients in `vbsec_ci_scan.py`.
- **E2E:** `e2e/tests/parser-parse-flow.spec.ts` — auth gate, validation, correlation header, OpenAPI parse paths.
- **Observability:** `request_context.py` + middleware; `log_event` injects `correlation_id`; background parse binds parent request id.

## Assumptions

- `continue-on-error: true` on SARIF upload avoids failing CI when GitHub Advanced Security is not licensed; vbsec JSON + scan step still gate merges.
- Deploy concurrency uses `cancel-in-progress: false` so in-flight production deploys are not killed by a newer push.

## Gitleaks CI credentials (2026-05-22)

- **Symptom:** GitHub Advanced Security flagged `generic-api-key` in `.github/workflows/ci-parser.yml` for hardcoded `API_KEY` / `JWT_SECRET` test literals.
- **Fix:** `scripts/ci/generate-parser-test-env.sh` emits ephemeral `openssl rand -hex 32` values; CI workflows source it; pytest uses `secrets.token_hex` in `conftest.py`; E2E writes `e2e/.parser-e2e.env` (gitignored) for Playwright.

## OpenAPI route descriptions (2026-05-22)

- Short usage-focused `summary` and `description` on each route (what the route is for, not status codes or env vars).
- Tag blurbs in `openapi_tags` on `app/main.py`. Visible at `/docs` when `EXPOSE_OPENAPI=true`.

## Parse document — unknown bankruptcy_id (2026-05-22)

- **Symptom:** Swagger default UUID (`3fa85f64-...`) caused FK 409 on `documents` insert, surfaced as **503**.
- **Fix:** `DocumentPipeline._require_bankruptcy()` checks `get_bankruptcy` before PDF work; `BankruptcyNotFoundError` → **422** with clear detail. Skipped when Supabase persistence is disabled (`_enabled` false).

## Parse 200 but empty `creditors` / `bankruptcy_creditors` (2026-05-22)

- **Symptom:** `POST /parse/document` returns 200; user sees no rows in “main” creditor tables. `documents` + `creditor_matrix_*` may still have rows.
- **Cause:** `au_group_merge_creditor_matrix` RPC fails on remote DB with `42P10` (missing `idx_creditors_normalized_name_address`). First parse can leave matrix rows; merge never runs; repeat requests hit content-hash cache and skip merge.
- **Fix:** Migration `20260522100000_ensure_creditors_merge_unique_index.sql`; `_backfill_creditor_merge` on cache hit; RPC errors raise `SupabaseUnavailableError`.
- **Ops:** Apply migration to hosted Supabase (`supabase db push` or SQL editor), then re-POST with `"force": true` or call the same parse again (backfill runs on cache).

## Supabase CLI migration history drift (2026-05-22)

- **Symptom:** `supabase db push` → “Remote migration versions not found in local migrations directory” (remote IDs like `20260515073354` vs local `20260215180000_*`).
- **Cause:** Cloud history was applied via dashboard/MCP with different version stamps than repo filenames; schema already matches.
- **Fix:** Reset `supabase_migrations.schema_migrations` on cloud to the 19 local migration versions (bookkeeping only, no SQL re-run). Helper: `scripts/supabase/repair-migration-history.sh` for future drift via CLI.

## CI dummy PDF smoke tests (2026-05-22)

- **Gap:** Unit tests mocked `DocumentPipeline`; integration tests need live `.env` and are skipped in `ci-parser`.
- **Added:** `tests/test_api_dummy_pdf_smoke.py` — real PyMuPDF dummy PDFs (`pdf_fixtures.py`), fake S3 download + in-memory Supabase (`fake_supabase.py`). Covers health, auth, parse/*, extract/*, review-queue, jobs.
- **CI:** `ci-parser.yml` runs `pytest -m smoke` after main suite.
