# Deploy-workflow investigation — Deploy Supabase migrations / Deploy document-parser (Railway)

**Date:** 2026-06-01
**Trigger:** Both workflows chronically red on every commit for ~1 week. Concern: KD-71's migration may never have auto-deployed to live.

## TL;DR

The red X has been **protecting** us, not just annoying us. Both deploy jobs fail on missing secrets, **and both deploy steps are redundant with the actual, working live-deploy mechanisms.** The naive fix (add the secrets) would have armed a live regression on the next migration-touching push to `main`.

- **KD-71 is functionally LIVE.** The live `au_group_list_company_creditors` exposes `normalized_name` — in a *better* form than the repo migration. The repo migration file was never applied and **must not be**.
- **Railway**: `document-parser` auto-deploys via Railway's **native GitHub source connection** (service `au-group` in project `au-group-be`, root `services/document-parser`). The `railway up` GH-Action step is dead weight.
- **Supabase**: the live DB is maintained by direct MCP `apply_migration`. The repo migrations dir has **diverged hard** from live (45 live-only, 10 repo-only). `supabase db push` would regress live.

## Root cause of the red

| Workflow | Failing step | Error | Cause |
|---|---|---|---|
| Deploy Supabase migrations | `deploy / Link and push migrations` | `Cannot find project ref. Have you run supabase link?` | `SUPABASE_ACCESS_TOKEN` / `SUPABASE_DB_PASSWORD` / `SUPABASE_PROJECT_REF` all empty |
| Deploy document-parser (Railway) | `deploy-production / Deploy to Railway` | `Invalid RAILWAY_TOKEN.` | `RAILWAY_TOKEN` empty |

Repo-level secrets: only `PROD` exists. `production` and `staging` GitHub environments have **zero** secrets. The referenced secrets simply don't exist. CI/security/codeql/trivy jobs all PASS — only the deploy jobs fail.

## Evidence

### KD-71 is already live (in superior form)

Live `au_group_list_company_creditors(p_bankruptcy_id uuid)` returns:
`creditor_id, creditor_name, normalized_name (2nd), creditor_address, claim_amount, creditor_state`
with `normalized_name = coalesce(nullif(trim(c.normalized_name),''), au_group_normalize_company_name(c.name))` and a `not au_group_is_suppressed_creditor_name(c.name)` filter.

Repo migration `20260603130001_kd71_list_company_creditors_normalized_name.sql` would `DROP`+recreate it returning `normalized_name` **last**, computed as `normalize(c.name)` only (no stored-column coalesce), **without** the suppression filter. Applying it = a live regression.

### Repo ↔ live migration drift

- **10 repo migrations NOT applied to live** (would run on next `db push`): `20260530120001`, `20260602150500/150600/150700/150800/150900`, `20260603120000/130000/130001/130002`.
- **45 migrations applied to live but NOT in the repo** (out-of-band MCP applies).
- Every genuinely-new object the 10 unapplied repo migrations would create **already exists in live** — verified: `salesforce_accounts.sf_recency_status` ✅, `creditors.company_tier` ✅, `processing_job_status` enum ✅ (`{queued,running,completed,failed,retrying}`), `au_group_enqueue_job`/`au_group_claim_job`/`au_group_active_target_states`/`au_group_daily_creditor_report_grouped` ✅, `au_group_merge_creditor_matrix` legacy 2-arg overload already dropped (1 overload). **No missing-and-needed change.**
- Note: migration *headers* claiming "does not exist on the live DB" (e.g. `sf_recency_status` in `20260603130000`) are **stale** — verify against live, don't trust the comment.

> `ci-supabase / migrate-reset` passing **masks** this drift: it only proves the repo migrations replay self-consistently on a fresh DB (producing the repo's inferior schema), not that they match prod. A DR/fresh rebuild would diverge from production.

### Railway native deploy is the working path

Service `au-group` (id `65d5c554-...`) in project `au-group-be` (id `06f5c757-...`):
- Source repo `Automation-Architecture/au-group`, root `services/document-parser`, builder Railpack.
- Latest **SUCCESS** deploy `caabb838-...` at `2026-06-01 04:46:14 UTC`, commit `7a259fa` — matches today's KD-71 push to `main`. Native source connection deploys on every push, independent of the failing GH Action.

## Recommended fix (asymmetric — the two are not the same problem)

**Railway `deploy-parser-railway.yml`** — low-stakes cleanup. Native deploy is permanent; drop the `railway up` deploy-staging/deploy-production jobs (+ dependent smoke gates) or make the workflow CI-only. Keep ci/security/codeql/trivy. Cron `smoke-e2e.yml` still covers post-deploy smoke.

**Supabase `deploy-supabase.yml`** — loaded footgun. Disable the `deploy` job (`if: false` + comment pointing at **KD-74**). Keep `ci` + `security`. Do **not** add the secrets. The real fix (reconcile repo↔live so the repo is a faithful mirror of prod) is **separate work** — tracked in **[KD-74](https://automationarchitecture.atlassian.net/browse/KD-74)**; not attempted in this pass.

**Docs to update to match reality:** `docs/ci/environments.md`, `docs/ci/rollback.md`, `docs/ci/requirements-traceability.md` all currently document these workflows as the deploy path.

This path writes **zero secrets**.

## Actions taken (this PR)

- `deploy-supabase.yml`: `deploy` job set `if: false` with a comment referencing KD-74. `ci` + `security` retained.
- `deploy-parser-railway.yml`: renamed to **document-parser CI**, deploy-staging / deploy-production / smoke-staging / smoke-production jobs removed; now CI-only (`ci` / `security` / `codeql` / `trivy`). Deploy continues via Railway's native source connection.
- Docs updated to match reality: `environments.md`, `rollback.md`, `requirements-traceability.md`.
- **KD-74** opened for the repo↔live migration reconciliation (the 45/10 drift).
